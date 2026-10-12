"""v3_1_0

Revision ID: a7c1d2e4f9b3
Revises: ec08ca6514ef
Create Date: 2026-10-12 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c1d2e4f9b3"
down_revision: Union[str, None] = "ec08ca6514ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("website", sa.Column("totp_secret", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("website", "totp_secret")
