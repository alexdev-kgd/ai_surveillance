"""rename email to login

Revision ID: 93b96c834a04
Revises: 
Create Date: 2026-05-11 15:14:10.895633

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '93b96c834a04'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column('users', 'email', new_column_name='login')

def downgrade():
    op.alter_column('users', 'login', new_column_name='email')
