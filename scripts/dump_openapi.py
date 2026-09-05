#!/usr/bin/env python3
"""Write the OpenAPI contract to docs/openapi.yaml.

The web frontend and the mobile application both generate their API client
from this file, so it must stay current. Run it after any route change:

    python scripts/dump_openapi.py

The script imports the FastAPI application. It does not start a server and it
does not touch the database.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# The application reads settings on import. Give it values that never reach a
# real service, so that this script runs anywhere.
os.environ.setdefault("HS_SECRET_KEY", "openapi-dump-only")
os.environ.setdefault("HS_DATABASE_URL", "postgresql+asyncpg://u:p@localhost/none")
os.environ.setdefault("HS_SERVE_MEDIA", "false")
os.environ.setdefault("HS_DATA_DIR", "/tmp")
os.environ.setdefault("HS_UPLOAD_DIR", "/tmp")
os.environ.setdefault("HS_BACKUP_DIR", "/tmp")
os.environ.setdefault("HS_CONFIG_DIR", "/tmp")


def main() -> int:
    import yaml

    from app.main import app

    spec = app.openapi()
    out_path = ROOT / "docs" / "openapi.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = (
        "# Generated file. Do not edit by hand.\n"
        "# Run: python scripts/dump_openapi.py\n"
        "#\n"
        "# The web frontend and the mobile application generate their API\n"
        "# client from this contract.\n"
    )
    body = yaml.safe_dump(
        json.loads(json.dumps(spec)), sort_keys=False, allow_unicode=True, width=100
    )
    out_path.write_text(header + body, encoding="utf-8")

    routes = len(spec.get("paths", {}))
    schemas = len(spec.get("components", {}).get("schemas", {}))
    print(f"Wrote {out_path.relative_to(ROOT)}: {routes} paths, {schemas} schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
