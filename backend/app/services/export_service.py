"""Export: CSV, insurance PDF, and the full ZIP backup.

The router layer reads the database and hands plain rows to this module, so
the export code stays independent of the ORM models.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import shutil
import tempfile
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import anyio.to_thread

from app.services.errors import BackupError

logger = logging.getLogger(__name__)

SCHEMA_VERSION: Final[str] = "1"
DEFAULT_CURRENCY: Final[str] = "AUD"

#: The column order of the CSV export and of the insurance report.
CSV_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "name",
    "description",
    "category",
    "subcategory",
    "brand",
    "model",
    "serial_number",
    "barcode",
    "location",
    "quantity",
    "condition",
    "purchase_price",
    "current_value",
    "purchase_date",
    "purchase_location",
    "warranty_expires",
    "is_lent",
    "lent_to",
    "lent_date",
    "tags",
    "notes",
    "created_at",
    "updated_at",
)


@dataclass(frozen=True, slots=True)
class ExportResult:
    """The result of one full export."""

    path: Path
    size_bytes: int
    entries: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the result as a plain dictionary."""
        return {
            "path": str(self.path),
            "filename": self.path.name,
            "size_bytes": self.size_bytes,
            "entries": list(self.entries),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class InsuranceReportOptions:
    """The tunable parts of the insurance report."""

    title: str = "Home Inventory — Insurance Report"
    owner: str | None = None
    currency: str = DEFAULT_CURRENCY
    include_photos: bool = True
    photo_width_mm: float = 22.0
    value_field: str = "current_value"
    fallback_value_field: str = "purchase_price"


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def items_to_csv(
    rows: Iterable[Mapping[str, Any]],
    *,
    columns: Sequence[str] = CSV_COLUMNS,
) -> bytes:
    """Return the items as CSV bytes, with a UTF-8 mark for Excel."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=list(columns), extrasaction="ignore", lineterminator="\r\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in columns})
    return buffer.getvalue().encode("utf-8-sig")


def _csv_value(value: Any) -> str:
    """Turn one field into text that a spreadsheet reads correctly."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, list | tuple | set):
        return ", ".join(str(entry) for entry in value)
    if isinstance(value, dict):
        return json.dumps(value, default=str)
    return str(value)


# --------------------------------------------------------------------------
# Insurance report (PDF)
# --------------------------------------------------------------------------


async def build_insurance_pdf(
    rows: Sequence[Mapping[str, Any]],
    *,
    options: InsuranceReportOptions | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    """Render the insurance report. The work runs in a worker thread."""
    opts = options or InsuranceReportOptions()
    moment = generated_at or datetime.now(UTC)
    return await anyio.to_thread.run_sync(
        lambda: _render_insurance_pdf(rows, opts, moment)
    )


def _render_insurance_pdf(
    rows: Sequence[Mapping[str, Any]],
    options: InsuranceReportOptions,
    generated_at: datetime,
) -> bytes:
    """Build the PDF with ReportLab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image as PDFImage,
        )
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
        )
    except ImportError as exc:  # pragma: no cover - the container installs it
        raise BackupError("ReportLab is not installed.") from exc

    styles = getSampleStyleSheet()
    cell = ParagraphStyle(
        "cell", parent=styles["BodyText"], fontSize=8, leading=10, spaceAfter=0
    )
    money = ParagraphStyle("money", parent=cell, alignment=TA_RIGHT)
    head = ParagraphStyle(
        "head", parent=cell, fontName="Helvetica-Bold", textColor=colors.white
    )

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=options.title,
        author="HomeStock",
    )

    total_value = sum(_row_value(row, options) or 0 for row in rows)
    story: list[Any] = [
        Paragraph(options.title, styles["Title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            f"Generated {generated_at.strftime('%d %B %Y at %H:%M %Z').strip()}",
            styles["Normal"],
        ),
    ]
    if options.owner:
        story.append(Paragraph(f"Owner: {options.owner}", styles["Normal"]))
    story += [
        Paragraph(f"Items listed: {len(rows)}", styles["Normal"]),
        Paragraph(
            f"Total declared value: {_money(total_value, options.currency)}",
            styles["Heading3"],
        ),
        Spacer(1, 4 * mm),
    ]

    summary = _category_summary(rows, options)
    if summary:
        story.append(Paragraph("Value by category", styles["Heading2"]))
        summary_table = Table(
            [["Category", "Items", f"Value ({options.currency})"]]
            + [[name, str(count), _amount(value)] for name, count, value in summary],
            colWidths=[90 * mm, 25 * mm, 40 * mm],
            hAlign="LEFT",
        )
        summary_table.setStyle(_table_style(colors, header_only=True))
        story += [summary_table, Spacer(1, 6 * mm), PageBreak()]

    story.append(Paragraph("Item detail", styles["Heading2"]))
    header = [
        "Photo",
        "Item",
        "Brand / model",
        "Serial",
        "Location",
        "Purchased",
        "Value",
    ]
    if not options.include_photos:
        header = header[1:]

    table_rows: list[list[Any]] = [[Paragraph(text, head) for text in header]]
    for row in rows:
        cells: list[Any] = []
        if options.include_photos:
            cells.append(_photo_flowable(row, options, PDFImage, mm))
        cells += [
            Paragraph(_escape(row.get("name")), cell),
            Paragraph(
                _escape(" ".join(filter(None, [row.get("brand"), row.get("model")]))),
                cell,
            ),
            Paragraph(_escape(row.get("serial_number")), cell),
            Paragraph(_escape(row.get("location")), cell),
            Paragraph(_escape(_csv_value(row.get("purchase_date"))), cell),
            Paragraph(_amount(_row_value(row, options)), money),
        ]
        table_rows.append(cells)

    widths = [26 * mm, 70 * mm, 55 * mm, 40 * mm, 45 * mm, 25 * mm, 25 * mm]
    if not options.include_photos:
        widths = widths[1:]

    detail = Table(table_rows, colWidths=widths, repeatRows=1)
    detail.setStyle(_table_style(colors))
    story.append(detail)

    document.build(story)
    return buffer.getvalue()


def _table_style(colors: Any, *, header_only: bool = False) -> Any:
    """Return the shared table style of the report."""
    from reportlab.platypus import TableStyle

    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if not header_only:
        commands.append(
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [colors.white, colors.HexColor("#f3f4f6")],
            )
        )
    return TableStyle(commands)


def _photo_flowable(
    row: Mapping[str, Any], options: InsuranceReportOptions, image_class: Any, mm: float
) -> Any:
    """Return the item photo, or an empty cell if there is no readable photo."""
    path_value = row.get("photo_path") or row.get("thumbnail_path")
    if not path_value:
        return ""
    path = Path(str(path_value))
    if not path.exists():
        return ""
    try:
        width = options.photo_width_mm * mm
        image = image_class(str(path))
        ratio = image.imageHeight / image.imageWidth if image.imageWidth else 1
        image.drawWidth = width
        image.drawHeight = width * ratio
        return image
    except Exception as exc:  # noqa: BLE001 - a bad photo must not stop the report
        logger.info("The report skipped the photo %s: %s", path, exc)
        return ""


def _category_summary(
    rows: Sequence[Mapping[str, Any]], options: InsuranceReportOptions
) -> list[tuple[str, int, float]]:
    """Group the values by category, largest value first."""
    totals: dict[str, list[float]] = {}
    for row in rows:
        name = str(row.get("category") or "Uncategorised")
        entry = totals.setdefault(name, [0.0, 0.0])
        entry[0] += 1
        entry[1] += _row_value(row, options) or 0.0
    return sorted(
        ((name, int(count), value) for name, (count, value) in totals.items()),
        key=lambda entry: entry[2],
        reverse=True,
    )


def _row_value(row: Mapping[str, Any], options: InsuranceReportOptions) -> float | None:
    """Return the insured value of one row."""
    for key in (options.value_field, options.fallback_value_field):
        value = row.get(key)
        if value is None:
            continue
        try:
            amount = float(value)
        except (TypeError, ValueError):
            continue
        quantity = row.get("quantity")
        try:
            factor = max(1, int(quantity)) if quantity is not None else 1
        except (TypeError, ValueError):
            factor = 1
        return amount * factor
    return None


def _amount(value: float | None) -> str:
    """Format one amount without the currency code."""
    return f"{value:,.2f}" if value else "—"


def _money(value: float, currency: str) -> str:
    """Format one amount with the currency code."""
    return f"{currency} {value:,.2f}"


def _escape(value: Any) -> str:
    """Escape text for a ReportLab paragraph."""
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------
# Full export (ZIP)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FullExportRequest:
    """Everything the full export needs from the caller."""

    destination: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    csv_bytes: bytes | None = None
    database_url: str | None = None
    uploads_dir: Path | None = None
    json_tables: Mapping[str, Sequence[Mapping[str, Any]]] | None = None
    include_uploads: bool = True


async def build_full_export(request: FullExportRequest) -> ExportResult:
    """Write one ZIP that holds the database, the uploads, and the metadata."""
    warnings: list[str] = []
    request.destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="homestock-export-") as workdir:
        work = Path(workdir)
        dump_path: Path | None = None
        if request.database_url:
            dump_path = work / "database.sql"
            error = await dump_database(request.database_url, dump_path)
            if error:
                warnings.append(error)
                dump_path = None

        return await anyio.to_thread.run_sync(
            lambda: _write_zip(request, dump_path, warnings)
        )


def _write_zip(
    request: FullExportRequest, dump_path: Path | None, warnings: list[str]
) -> ExportResult:
    """Build the ZIP file itself."""
    entries: list[str] = []
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        **request.metadata,
    }

    try:
        with zipfile.ZipFile(
            request.destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            if dump_path and dump_path.exists():
                archive.write(dump_path, "database.sql")
                entries.append("database.sql")

            if request.json_tables:
                payload = json.dumps(
                    request.json_tables, indent=2, default=_json_default
                )
                archive.writestr("database.json", payload)
                entries.append("database.json")

            if request.csv_bytes:
                archive.writestr("inventory-report.csv", request.csv_bytes)
                entries.append("inventory-report.csv")

            if request.include_uploads and request.uploads_dir:
                count = _add_uploads(archive, request.uploads_dir)
                metadata["upload_file_count"] = count
                if count:
                    entries.append(f"uploads/ ({count} files)")

            archive.writestr(
                "metadata.json", json.dumps(metadata, indent=2, default=_json_default)
            )
            entries.append("metadata.json")
    except OSError as exc:
        raise BackupError(f"The export could not be written: {exc}") from exc

    return ExportResult(
        path=request.destination,
        size_bytes=request.destination.stat().st_size,
        entries=tuple(entries),
        warnings=tuple(warnings),
    )


def _add_uploads(archive: zipfile.ZipFile, uploads_dir: Path) -> int:
    """Add every uploaded file to the archive under `uploads/`."""
    if not uploads_dir.exists():
        return 0
    count = 0
    for path in sorted(uploads_dir.rglob("*")):
        if path.is_file():
            archive.write(path, str(Path("uploads") / path.relative_to(uploads_dir)))
            count += 1
    return count


async def dump_database(database_url: str, destination: Path) -> str | None:
    """Run pg_dump into `destination`. Return a warning text on failure."""
    if shutil.which("pg_dump") is None:
        return "pg_dump is not installed, so the export holds database.json only."

    args, env = _pg_dump_command(database_url)
    try:
        with destination.open("wb") as handle:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=handle,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            _, stderr = await process.communicate()
    except OSError as exc:
        return f"pg_dump could not start: {exc}"

    if process.returncode != 0:
        message = stderr.decode("utf-8", "replace").strip()[:300]
        logger.warning("pg_dump failed: %s", message)
        return f"pg_dump failed: {message}"
    return None


def _pg_dump_command(database_url: str) -> tuple[list[str], dict[str, str]]:
    """Turn a SQLAlchemy URL into a pg_dump command and its environment."""
    from sqlalchemy.engine import make_url

    url = make_url(database_url)
    args = ["pg_dump", "--no-owner", "--no-privileges", "--format=plain"]
    if url.host:
        args += ["--host", url.host]
    if url.port:
        args += ["--port", str(url.port)]
    if url.username:
        args += ["--username", url.username]
    if url.database:
        args += ["--dbname", url.database]

    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = str(url.password)
    return args, env


def _json_default(value: Any) -> str:
    """Serialise the types that JSON does not know."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID | Decimal | Path):
        return str(value)
    return repr(value)


def export_filename(
    prefix: str = "homestock-backup", moment: datetime | None = None
) -> str:
    """Return a timestamped filename such as homestock-backup-20260905-0300.zip."""
    stamp = (moment or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}.zip"


__all__ = [
    "CSV_COLUMNS",
    "SCHEMA_VERSION",
    "ExportResult",
    "FullExportRequest",
    "InsuranceReportOptions",
    "build_full_export",
    "build_insurance_pdf",
    "dump_database",
    "export_filename",
    "items_to_csv",
]
