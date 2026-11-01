"""join the heads that other branches depend on (FOLLOWUP-57/132, step 1 of 2)

03a_0001, 03b_0001, 06a_0002 and 07_0001 are heads of the script but have no row of their own in
`alembic_version`: other revisions name them in `depends_on`, so Alembic folds them into the
dependent rows ("effective head"). Alembic 1.20's merge step deletes the row of every parent
without checking that it exists, so one merge over all eight package heads fails with
`KeyError: '03a_0001'`. This step joins the four row-less heads first; when it runs none of its
parents is a row, so Alembic inserts a new row for it. Step 2 (57_0002) merges this row with the
four package heads that do have rows. No schema change.

Revision ID: 57_0001
Revises: 03a_0001, 03b_0001, 06a_0002, 07_0001
Create Date: 2026-11-01
"""

revision = "57_0001"
down_revision = ("03a_0001", "03b_0001", "06a_0002", "07_0001")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
