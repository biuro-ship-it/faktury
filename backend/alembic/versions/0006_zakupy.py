"""zakupy: numer faktury dostawcy obowiazkowy po zatwierdzeniu i unikalny u dostawcy

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-08 21:30:00

Faktura zakupu to ten sam `dokument` co faktura sprzedazy (typ `faktura_zakupu` byl dozwolony juz w 0005),
wiec ta migracja dodaje tylko dwa zabezpieczenia w bazie:
- zatwierdzona faktura zakupu musi miec numer dostawcy (CHECK),
- ten sam numer dostawcy nie moze wejsc do ewidencji dwa razy (unikalnosc czesciowa; anulowana faktura
  zwalnia numer).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        op.f('ck_dokument_zakup_numer_obcy'), 'dokument',
        "typ <> 'faktura_zakupu' OR status = 'szkic' OR length(btrim(numer_obcy)) > 0",
    )
    op.create_index(
        'uq_dokument_zakupu_numer_obcy', 'dokument', ['kontrahent_id', 'numer_obcy'], unique=True,
        postgresql_where=sa.text("typ = 'faktura_zakupu' AND status <> 'anulowany' AND numer_obcy <> ''"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'uq_dokument_zakupu_numer_obcy', table_name='dokument',
        postgresql_where=sa.text("typ = 'faktura_zakupu' AND status <> 'anulowany' AND numer_obcy <> ''"),
    )
    op.drop_constraint(op.f('ck_dokument_zakup_numer_obcy'), 'dokument', type_='check')
