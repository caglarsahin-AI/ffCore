"""merge the package branch heads into one head (FOLLOWUP-57/132, step 2 of 2)

After this revision `alembic heads` prints one line and `alembic upgrade head` works; the migrate
service's `alembic upgrade heads` is unchanged. A new package revision starts from this head
(down_revision = the current single head) under its own branch label. No schema change.

Merged branches can no longer be rolled back with `<label>@-1` or `downgrade -1`: Alembic cannot
walk down relatively from a merge point ("Ambiguous walk"). Roll back with an explicit revision:
`alembic downgrade <revision to keep>` removes everything above it, including the merge
revisions (docs/gelistirme-ortami.md).

Revision ID: 57_0002
Revises: 57_0001, 03c_0002, 04a_0001, 05a_0001, 08_0001
Create Date: 2026-11-01
"""

revision = "57_0002"
down_revision = ("57_0001", "03c_0002", "04a_0001", "05a_0001", "08_0001")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
