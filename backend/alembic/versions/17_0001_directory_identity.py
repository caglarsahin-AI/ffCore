"""17: directory identity (`users` columns, `project_members.membership_source`,
`identity_group_mappings`)

Revision ID: 17_0001
Revises: 16_0001
Create Date: 2026-11-23

- `users.auth_source` (local | ldap | oidc, default local), `external_id` (objectGUID /
  entryUUID / OIDC `sub`), `last_login_at`, `must_change_password`. `password_hash` becomes
  nullable: a directory account has no password (CHECK `password_only_local`). A superadmin is
  always local (CHECK `superadmin_is_local`, brief 17 recovery account).
- `project_members.membership_source` (manual | idp, default manual): group sync touches only
  `idp` rows; a manual membership is authoritative (K-17-0002 S2).
- `identity_group_mappings`: group -> project role; project_id required (K-17-0002 S3), common
  C3 columns, soft delete.

Additive except the NOT NULL relaxation of `password_hash`. The downgrade refuses while any
directory account exists (it would need a password it never had; no silent data loss).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# Check constraint names are full (op.f): the naming convention would prefix them again.

revision = "17_0001"
down_revision = "16_0001"
branch_labels = ("17",)
depends_on = None

AUTH_SOURCES = ("local", "ldap", "oidc")
EXTERNAL_PROVIDERS = ("ldap", "oidc")
MEMBERSHIP_SOURCES = ("manual", "idp")
DEACTIVATED_BY = ("identity_sync", "admin")
# ck_alert_rules_kind: 03c_0002's list (+ 16's prune_refused was already in it) and 17's kind.
ALERT_KINDS = (
    "budget_threshold",
    "service_down",
    "ingest_error",
    "sync_error",
    "prune_refused",
    "approval_pending_age",
    "guardrail_block_rate",
    "quota_warn",
    "convert_timeout",
    "disk_memory",
    "checkpoint_purge_overdue",
)
ALERT_KINDS_17 = (*ALERT_KINDS, "identity_sync_refused")


def _in(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


ASSIGNABLE_ROLES = ("user", "analyst", "admin")
ACCESS_MODES = ("edit", "read")


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("auth_source", sa.Text(), nullable=False, server_default="local")
    )
    op.add_column("users", sa.Column("external_id", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("deactivated_by", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_users_deactivated_by"),
        "users",
        f"deactivated_by IS NULL OR deactivated_by IN {DEACTIVATED_BY}",
    )
    # r2: the identity_sync_refused alert kind (additive value of 03c's list).
    op.drop_constraint(op.f("ck_alert_rules_kind"), "alert_rules", type_="check")
    op.create_check_constraint(
        op.f("ck_alert_rules_kind"), "alert_rules", _in("kind", ALERT_KINDS_17)
    )
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint(
        op.f("ck_users_auth_source"), "users", f"auth_source IN {AUTH_SOURCES}"
    )
    op.create_check_constraint(
        op.f("ck_users_password_only_local"),
        "users",
        "(auth_source = 'local') = (password_hash IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_users_superadmin_is_local"), "users", "NOT is_superadmin OR auth_source = 'local'"
    )
    op.create_index(
        "uq_users_external_id_live",
        "users",
        ["auth_source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL AND deleted_at IS NULL"),
    )

    op.add_column(
        "project_members",
        sa.Column("membership_source", sa.Text(), nullable=False, server_default="manual"),
    )
    op.create_check_constraint(
        op.f("ck_project_members_membership_source"),
        "project_members",
        f"membership_source IN {MEMBERSHIP_SOURCES}",
    )

    op.create_table(
        "identity_group_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_group", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("access", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"provider IN {EXTERNAL_PROVIDERS}", name="provider"),
        sa.CheckConstraint(f"role IN {ASSIGNABLE_ROLES}", name="role"),
        sa.CheckConstraint(f"access IN {ACCESS_MODES}", name="access"),
        sa.CheckConstraint("length(external_group) BETWEEN 1 AND 1024", name="external_group"),
    )
    op.create_index(
        "uq_identity_group_mappings_live",
        "identity_group_mappings",
        ["provider", "external_group", "project_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_identity_group_mappings_project", "identity_group_mappings", ["project_id"])


def downgrade() -> None:
    external = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM users WHERE auth_source <> 'local'")
    )
    if external:
        raise RuntimeError(
            f"17_0001 downgrade refused: {external} directory account(s) exist; they have no "
            "password and would break password_hash NOT NULL. Delete or convert them first."
        )
    rules = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM alert_rules WHERE kind = 'identity_sync_refused'")
    )
    if rules:
        raise RuntimeError(
            f"17_0001 downgrade refused: {rules} alert rule(s) of kind identity_sync_refused "
            "exist; delete them first."
        )
    op.drop_constraint(op.f("ck_alert_rules_kind"), "alert_rules", type_="check")
    op.create_check_constraint(op.f("ck_alert_rules_kind"), "alert_rules", _in("kind", ALERT_KINDS))
    op.drop_constraint(op.f("ck_users_deactivated_by"), "users", type_="check")
    op.drop_column("users", "deactivated_by")
    op.drop_index("ix_identity_group_mappings_project", table_name="identity_group_mappings")
    op.drop_index("uq_identity_group_mappings_live", table_name="identity_group_mappings")
    op.drop_table("identity_group_mappings")
    op.drop_constraint(
        op.f("ck_project_members_membership_source"), "project_members", type_="check"
    )
    op.drop_column("project_members", "membership_source")
    op.drop_index("uq_users_external_id_live", table_name="users")
    op.drop_constraint(op.f("ck_users_superadmin_is_local"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_password_only_local"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_auth_source"), "users", type_="check")
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "external_id")
    op.drop_column("users", "auth_source")
