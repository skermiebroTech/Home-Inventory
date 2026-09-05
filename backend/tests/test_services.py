"""Unit tests for the service layer and the utilities.

None of these tests reach the network. The AI tests use a fake transport, so
that the suite runs with no Ollama server.
"""

from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from PIL import Image

pytestmark = pytest.mark.asyncio(loop_scope="session")


# --------------------------------------------------------------------------
# Reading the model answer
# --------------------------------------------------------------------------


def test_extract_json_reads_a_plain_array() -> None:
    from app.services.ai_service import extract_json_payload

    assert extract_json_payload('[{"name": "Drill"}]') == [{"name": "Drill"}]


def test_extract_json_reads_a_fenced_block() -> None:
    from app.services.ai_service import extract_json_payload

    text = 'Here you are:\n```json\n{"items": [{"name": "Drill"}]}\n```\nThanks.'
    assert extract_json_payload(text) == {"items": [{"name": "Drill"}]}


def test_extract_json_reads_an_object_after_prose() -> None:
    from app.services.ai_service import extract_json_payload

    text = 'I found one item. {"name": "Hammer", "brand": null} That is all.'
    assert extract_json_payload(text) == {"name": "Hammer", "brand": None}


def test_extract_json_returns_none_for_prose() -> None:
    from app.services.ai_service import extract_json_payload

    assert extract_json_payload("I cannot see the image.") is None


def test_parse_suggestion_normalises_the_fields() -> None:
    from app.services.ai_service import parse_suggestion

    suggestion = parse_suggestion(
        {
            "name": "DeWalt DCD771 cordless drill",
            "brand": "DeWalt",
            "category": "Tools",
            "estimated_value_aud": "A$199.00",
            "condition": "Good condition",
            "region": [10, 20, 30, 40],
        }
    )
    assert suggestion is not None
    assert suggestion.estimated_value_aud == 199.0
    assert suggestion.condition == "good"
    assert suggestion.region == (10, 20, 30, 40)
    assert suggestion.to_item_payload()["current_value"] == 199.0


def test_parse_suggestion_needs_a_name() -> None:
    from app.services.ai_service import parse_suggestion

    assert parse_suggestion({"brand": "DeWalt"}) is None


def test_a_region_of_words_is_dropped() -> None:
    from app.services.ai_service import parse_region

    assert parse_region({"region": "the top shelf"}) is None


def test_the_prompts_match_the_specification() -> None:
    from app.services.ai_service import ITEM_RECOGNITION_PROMPT, RECEIPT_PARSE_PROMPT

    assert ITEM_RECOGNITION_PROMPT.startswith("You are a home inventory assistant.")
    assert "estimated_value_aud (number)" in ITEM_RECOGNITION_PROMPT
    assert "condition (new/good/fair/poor)" in ITEM_RECOGNITION_PROMPT
    assert RECEIPT_PARSE_PROMPT.startswith("Parse this receipt image.")
    assert "grand_total, currency" in RECEIPT_PARSE_PROMPT


# --------------------------------------------------------------------------
# The AI service against a fake Ollama
# --------------------------------------------------------------------------


async def test_recognize_reads_the_model_answer() -> None:
    from app.services.ai_service import AIService, OllamaConfig

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            return _holds(32768)
        assert request.url.path == "/api/generate"
        body = request.read().decode()
        assert "home inventory assistant" in body
        return httpx.Response(
            200,
            json={
                "response": '[{"name": "DeWalt DCD771 cordless drill", '
                '"brand": "DeWalt", "estimated_value_aud": 199, '
                '"condition": "good"}]'
            },
        )

    service = AIService(OllamaConfig(base_url="http://ollama.test"))
    transport = httpx.MockTransport(handler)
    service._client = lambda **_: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=transport, base_url="http://ollama.test"
    )

    result = await service.recognize(b"fake image bytes")
    assert [s.name for s in result.suggestions] == ["DeWalt DCD771 cordless drill"]
    assert result.suggestions[0].estimated_value_aud == 199.0


async def test_the_ai_service_reports_a_closed_port_instead_of_raising() -> None:
    from app.services.ai_service import AIService, OllamaConfig

    service = AIService(
        OllamaConfig(base_url="http://127.0.0.1:1", timeout=1, enabled=True)
    )
    status = await service.status()
    assert status.available is False
    assert status.error


async def test_a_turned_off_ai_refuses_the_call() -> None:
    from app.services.ai_service import AIService, OllamaConfig
    from app.services.errors import AIUnavailableError

    service = AIService(OllamaConfig(enabled=False))
    with pytest.raises(AIUnavailableError):
        await service.recognize(b"image")


# --------------------------------------------------------------------------
# The receipt fallback parser
# --------------------------------------------------------------------------


def test_the_text_parser_reads_a_receipt() -> None:
    from app.services.ocr_service import parse_receipt_text

    text = """
    BUNNINGS WAREHOUSE
    Slacks Creek QLD
    12/03/2026

    Timber pine 90x45      24.50
    Deck screws 100pk      18.95
    SUBTOTAL               43.45
    GST                     4.35
    TOTAL                  47.80
    EFTPOS                 47.80
    """
    parsed = parse_receipt_text(text)
    assert parsed.store_name == "BUNNINGS WAREHOUSE"
    assert parsed.purchase_date == date(2026, 3, 12)
    assert parsed.subtotal == 43.45
    assert parsed.tax == 4.35
    assert parsed.grand_total == 47.80
    assert parsed.currency == "AUD"
    assert [line.name for line in parsed.lines] == [
        "Timber pine 90x45",
        "Deck screws 100pk",
    ]


def test_the_text_parser_survives_an_empty_page() -> None:
    from app.services.ocr_service import parse_receipt_text

    parsed = parse_receipt_text("")
    assert parsed.store_name is None
    assert parsed.grand_total is None
    assert parsed.lines == ()


def test_dates_are_read_day_first() -> None:
    from app.services.ocr_service import parse_date

    assert parse_date("2026-03-12") == date(2026, 3, 12)
    assert parse_date("12/03/2026") == date(2026, 3, 12)
    assert parse_date("12 Mar 2026") == date(2026, 3, 12)
    assert parse_date("not a date") is None


# --------------------------------------------------------------------------
# Barcodes
# --------------------------------------------------------------------------


def test_barcode_normalisation() -> None:
    from app.services.barcode_service import InvalidBarcodeError, normalise_barcode

    assert normalise_barcode(" 93 361 391 ") == "93361391"
    assert normalise_barcode("9310072030006") == "9310072030006"
    with pytest.raises(InvalidBarcodeError):
        normalise_barcode("abc")
    with pytest.raises(InvalidBarcodeError):
        normalise_barcode("123")


async def test_barcode_lookup_reads_open_food_facts() -> None:
    from app.services.barcode_service import BarcodeService

    def handler(request: httpx.Request) -> httpx.Response:
        assert "openfoodfacts" in str(request.url)
        return httpx.Response(
            200,
            json={
                "status": 1,
                "product": {
                    "product_name": "Vegemite 380g",
                    "brands": "Bega,Kraft",
                    "categories": "Spreads,Yeast extracts",
                    "quantity": "380 g",
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        product = await BarcodeService(client=http).lookup("9300650001234")

    assert product is not None
    assert product.name == "Vegemite 380g"
    assert product.brand == "Bega"
    assert product.category == "Spreads"
    assert product.source == "openfoodfacts"


async def test_barcode_lookup_returns_none_when_no_database_knows_it() -> None:
    from app.services.barcode_service import BarcodeService

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"status": 0})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await BarcodeService(client=http).lookup("9300650001234") is None


# --------------------------------------------------------------------------
# Images and labels
# --------------------------------------------------------------------------


def test_thumbnail_widths_are_read_from_a_string() -> None:
    from app.utils.thumbnails import parse_widths

    assert parse_widths("200,600") == (200, 600)
    assert parse_widths([600, 200]) == (200, 600)
    assert parse_widths("nonsense") == (200, 600)


def test_store_image_resizes_and_writes_the_thumbnails(tmp_path: Path) -> None:
    from app.utils.thumbnails import ImageOptions, store_image_sync

    buffer = io.BytesIO()
    Image.new("RGB", (3000, 1500), "sienna").save(buffer, format="JPEG")

    stored = store_image_sync(
        buffer.getvalue(),
        directory=tmp_path,
        options=ImageOptions(max_dimension=2000, thumbnail_widths=(200, 600)),
        stem="photo",
    )
    assert stored.width == 2000
    assert set(stored.thumbnails) == {200, 600}
    with Image.open(stored.thumbnails[600]) as thumbnail:
        assert thumbnail.width == 600


def test_store_image_refuses_a_file_that_is_not_an_image(tmp_path: Path) -> None:
    from app.utils.thumbnails import UnsupportedImageError, store_image_sync

    with pytest.raises(UnsupportedImageError):
        store_image_sync(b"this is not a picture", directory=tmp_path)


def test_the_qr_code_holds_the_item_address() -> None:
    from app.utils.qr import generate_qr_png, qr_payload

    payload = qr_payload(
        "item", "11111111-2222-4333-8444-555555555555", "http://nas:7850"
    )
    assert payload == "http://nas:7850/items/11111111-2222-4333-8444-555555555555"

    png = generate_qr_png(payload, caption="Cordless drill", width=256)
    assert png.startswith(b"\x89PNG")
    with Image.open(io.BytesIO(png)) as image:
        assert image.width == 256


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


def test_items_to_csv_writes_a_header_and_a_row() -> None:
    from app.services.export_service import items_to_csv

    csv_bytes = items_to_csv(
        [
            {
                "id": "abc",
                "name": "Drill",
                "tags": ["Tools", "Loud"],
                "is_lent": True,
                "purchase_date": date(2026, 1, 5),
            }
        ]
    )
    text = csv_bytes.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("id,name,description")
    assert "Drill" in text
    assert "Tools, Loud" in text
    assert "yes" in text
    assert "2026-01-05" in text


async def test_the_insurance_report_is_a_pdf() -> None:
    from app.services.export_service import build_insurance_pdf

    pdf = await build_insurance_pdf(
        [
            {
                "name": "Drill",
                "brand": "DeWalt",
                "category": "Tools",
                "current_value": 199,
                "quantity": 1,
            }
        ]
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


# --------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------


def test_a_bad_cron_expression_is_refused() -> None:
    from app.services.backup_service import validate_cron
    from app.services.errors import ValidationError

    validate_cron("0 3 * * *")
    with pytest.raises(ValidationError):
        validate_cron("every night please")


async def test_the_retention_rule_keeps_the_newest_archives(tmp_path: Path) -> None:
    import os
    import time

    from app.services.backup_service import BackupConfig, BackupService

    service = BackupService(
        lambda path: None,  # type: ignore[arg-type,return-value]
        config=BackupConfig(backup_dir=tmp_path, config_dir=tmp_path, retention=2),
    )
    for index in range(4):
        archive = tmp_path / f"homestock-backup-2026090{index}-000000.zip"
        archive.write_bytes(b"zip")
        stamp = time.time() + index
        os.utime(archive, (stamp, stamp))

    deleted = service.apply_retention()
    assert len(deleted) == 2
    assert len(service.list_backups()) == 2


def test_a_line_keeps_its_amount_when_the_model_fills_one_field() -> None:
    from app.services.ocr_service import build_parsed_receipt

    parsed = build_parsed_receipt(
        {
            "store_name": "Bunnings",
            "items": [
                {"name": "Screws", "quantity": 2, "unit_price": 9.5, "total": None},
                {"name": "Glue", "quantity": 3, "unit_price": None, "total": 12.0},
                {"name": "Tape", "quantity": None, "unit_price": 4.25, "total": None},
            ],
        }
    )
    assert [line.total for line in parsed.lines] == [19.0, 12.0, 4.25]
    assert parsed.lines[1].unit_price == 4.0


# --------------------------------------------------------------------------
# Reading the text on a photograph
# --------------------------------------------------------------------------


async def test_the_text_of_several_photographs_is_labelled() -> None:
    from app.services.ocr_service import OCRService

    service = OCRService()
    pages = iter(["DEWALT DCD771\nTYPE 1", "  ", "S/N 4821994"])

    async def fake_extract(_image: bytes) -> str:
        return next(pages)

    service.extract_text = fake_extract  # type: ignore[method-assign]

    text = await service.extract_text_many([b"a", b"b", b"c"])
    # The empty page drops out, and the numbering follows the photographs.
    assert "Photograph 1:\nDEWALT DCD771" in text
    assert "Photograph 3:\nS/N 4821994" in text
    assert "Photograph 2" not in text


def _holds(tokens: int) -> httpx.Response:
    """The answer of POST /api/show: how many tokens the model holds."""
    return httpx.Response(200, json={"model_info": {"phi2.context_length": tokens}})


async def test_recognize_sends_every_photograph_and_the_read_text() -> None:
    from app.services.ai_service import AIService, OllamaConfig

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            return _holds(32768)
        body = json.loads(request.read())
        seen["images"] = len(body["images"])
        seen["prompt"] = body["prompt"]
        return httpx.Response(
            200,
            json={
                "response": '[{"name": "DeWalt DCD771 cordless drill", '
                '"brand": "DeWalt", "model": "DCD771", '
                '"serial_number": "4821994", "condition": "good"}]'
            },
        )

    service = AIService(OllamaConfig(base_url="http://ollama.test"))
    transport = httpx.MockTransport(handler)
    service._client = lambda **_: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=transport, base_url="http://ollama.test"
    )

    result = await service.recognize(
        [b"front", b"plate"], ocr_text="Photograph 2:\nDEWALT DCD771 S/N 4821994"
    )

    assert seen["images"] == 2
    prompt = str(seen["prompt"])
    # The prompt of the specification stays first, and the extra parts follow.
    assert prompt.startswith("You are a home inventory assistant.")
    assert "same one item" in prompt
    assert "serial_number" in prompt
    assert "S/N 4821994" in prompt

    assert result.image_count == 2
    suggestion = result.suggestions[0]
    assert suggestion.model == "DCD771"
    assert suggestion.serial_number == "4821994"
    assert suggestion.to_item_payload()["serial_number"] == "4821994"


async def test_a_small_context_gets_one_photograph_and_the_plain_prompt() -> None:
    """A model that cannot hold it all still answers.

    moondream holds 2048 tokens and one photograph costs about 1700 of them,
    so two photographs and the read text can never fit. The second call drops
    both instead of failing.
    """
    from app.services.ai_service import AIService, OllamaConfig

    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            return _holds(2048)
        calls.append(json.loads(request.read()))
        return httpx.Response(200, json={"response": '[{"name": "Mower"}]'})

    service = AIService(OllamaConfig(base_url="http://ollama.test"))
    transport = httpx.MockTransport(handler)
    service._client = lambda **_: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=transport, base_url="http://ollama.test"
    )

    result = await service.recognize([b"front", b"plate"], ocr_text="HRU19")

    # One call, already cut to fit: one photograph, and no read text beside it.
    assert len(calls) == 1
    assert len(calls[0]["images"]) == 1  # type: ignore[arg-type]
    assert "HRU19" not in str(calls[0]["prompt"])
    assert "same one item" not in str(calls[0]["prompt"])
    assert result.suggestions[0].name == "Mower"


async def test_a_small_context_with_nothing_left_to_drop_reports_it() -> None:
    from app.services.ai_service import AIService, ContextTooSmallError, OllamaConfig

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            return _holds(2048)
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "request (2312 tokens) exceeds the available "
                    "context size (2048 tokens)",
                    "type": "exceed_context_size_error",
                }
            },
        )

    service = AIService(OllamaConfig(base_url="http://ollama.test"))
    transport = httpx.MockTransport(handler)
    service._client = lambda **_: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=transport, base_url="http://ollama.test"
    )

    with pytest.raises(ContextTooSmallError) as caught:
        await service.recognize([b"front"])
    assert "exceeds the available context size" in str(caught.value)


async def test_the_read_text_stays_short_for_the_vision_model() -> None:
    from app.services.ai_service import VISION_TEXT_LIMIT, AIService, OllamaConfig

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            return _holds(32768)
        seen["prompt"] = json.loads(request.read())["prompt"]
        return httpx.Response(200, json={"response": '[{"name": "Drill"}]'})

    service = AIService(OllamaConfig(base_url="http://ollama.test"))
    transport = httpx.MockTransport(handler)
    service._client = lambda **_: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=transport, base_url="http://ollama.test"
    )

    await service.recognize([b"front"], ocr_text="x" * 5000)
    prompt = seen["prompt"]
    assert "x" * VISION_TEXT_LIMIT in prompt
    assert "x" * (VISION_TEXT_LIMIT + 1) not in prompt


async def test_one_photograph_does_not_get_the_multi_angle_line() -> None:
    from app.services.ai_service import AIService, OllamaConfig

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            return _holds(32768)
        seen["prompt"] = json.loads(request.read())["prompt"]
        return httpx.Response(200, json={"response": "[]"})

    service = AIService(OllamaConfig(base_url="http://ollama.test"))
    transport = httpx.MockTransport(handler)
    service._client = lambda **_: httpx.AsyncClient(  # type: ignore[method-assign]
        transport=transport, base_url="http://ollama.test"
    )

    await service.recognize(b"only one")
    assert "same one item" not in seen["prompt"]
