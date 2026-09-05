"""Give every item a seven digit asset tag.

The tag is the number on the sticker. A person can read it out, and the QR
code holds a short address that ends with it instead of a UUID, which makes
the code far less dense.

A PostgreSQL sequence hands the numbers out. That way every way of making an
item gets one, including a push from a phone that was offline, and two
requests at the same moment cannot take the same number.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The form that PostgreSQL stores, so that "alembic check" stays quiet.
DEFAULT = "lpad((nextval('items_asset_tag_seq'::regclass))::text, 7, '0'::text)"


def upgrade() -> None:
    """Add the sequence, the column, and a number for every item."""
    op.execute("CREATE SEQUENCE IF NOT EXISTS items_asset_tag_seq START 1")

    # The column arrives without the rule, so the rows that already exist can
    # take their numbers in the order that they were made.
    op.add_column("items", sa.Column("asset_tag", sa.String(length=7), nullable=True))
    op.execute(
        """
        UPDATE items AS target
           SET asset_tag = lpad(numbered.place::text, 7, '0')
          FROM (
                SELECT id, row_number() OVER (ORDER BY created_at, id) AS place
                  FROM items
               ) AS numbered
         WHERE target.id = numbered.id
        """
    )
    # The next new item carries on from the highest number in use.
    op.execute(
        "SELECT setval('items_asset_tag_seq', GREATEST((SELECT count(*) FROM items), 1))"
    )

    op.alter_column("items", "asset_tag", nullable=False)
    op.alter_column("items", "asset_tag", server_default=sa.text(DEFAULT))
    op.create_index("ix_items_asset_tag", "items", ["asset_tag"], unique=True)


def downgrade() -> None:
    """Drop the column and the sequence."""
    op.drop_index("ix_items_asset_tag", table_name="items")
    op.drop_column("items", "asset_tag")
    op.execute("DROP SEQUENCE IF EXISTS items_asset_tag_seq")
