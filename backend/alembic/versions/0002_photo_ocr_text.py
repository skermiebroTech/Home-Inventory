"""Add the OCR text of an item photograph.

A photograph of a rating plate, a label, or a box carries the exact model and
the serial number. The upload route reads that text with Tesseract after it
answers, and keeps it here.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the column."""
    op.add_column("item_photos", sa.Column("ocr_text", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove the column."""
    op.drop_column("item_photos", "ocr_text")
