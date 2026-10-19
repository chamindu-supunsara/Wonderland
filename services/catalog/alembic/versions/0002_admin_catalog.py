"""Administrator revisions, stable seed identity and audit records.

Revision ID: 0002_admin_catalog
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_admin_catalog"
down_revision = "0001_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("attractions", sa.Column("revision", sa.Integer(), server_default="1", nullable=False), schema="catalog")
    op.add_column("attractions", sa.Column("seed_key", sa.String(40), nullable=True), schema="catalog")
    op.create_unique_constraint("uq_attraction_seed_key", "attractions", ["seed_key"], schema="catalog")
    op.create_check_constraint("ck_attraction_revision", "attractions", "revision > 0", schema="catalog")
    # Link existing foundation records before administrators can rename them.
    for name, key in [("Skyline Rush", "skyline-rush"), ("Little Explorers", "little-explorers"), ("River Rapids", "river-rapids"), ("Wonder Quest", "wonder-quest")]:
        op.execute(sa.text("UPDATE catalog.attractions SET seed_key=:key WHERE id = (SELECT id FROM catalog.attractions WHERE name=:name ORDER BY created_at, id LIMIT 1)").bindparams(key=key, name=name))
    op.add_column("ticket_prices", sa.Column("created_by", sa.String(128), nullable=True), schema="catalog")
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="catalog",
    )
    op.create_index("ix_catalog_audit_events_resource_id", "audit_events", ["resource_id"], schema="catalog")


def downgrade():
    op.drop_table("audit_events", schema="catalog")
    op.drop_column("ticket_prices", "created_by", schema="catalog")
    op.drop_constraint("ck_attraction_revision", "attractions", schema="catalog")
    op.drop_constraint("uq_attraction_seed_key", "attractions", schema="catalog")
    op.drop_column("attractions", "seed_key", schema="catalog")
    op.drop_column("attractions", "revision", schema="catalog")
