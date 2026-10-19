"""Initial catalog tables and pricing constraints.

Revision ID: 0001_catalog
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_catalog"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # The local/cloud database bootstrap creates the schema and service role.
    op.create_table(
        "attractions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("thrill_level", sa.String(20), nullable=False),
        sa.Column("min_age", sa.Integer(), nullable=True),
        sa.Column("min_height_cm", sa.Integer(), nullable=True),
        sa.Column("guidance_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("min_age IS NULL OR min_age >= 0", name="ck_attraction_age"),
        sa.CheckConstraint("min_height_cm IS NULL OR min_height_cm >= 0", name="ck_attraction_height"),
        sa.CheckConstraint("status IN ('ACTIVE', 'RETIRED')", name="ck_attraction_status"),
        schema="catalog",
    )
    op.create_index("ix_catalog_attractions_category", "attractions", ["category"], schema="catalog")
    op.create_index("ix_catalog_attractions_status", "attractions", ["status"], schema="catalog")
    op.create_table(
        "ticket_tiers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("min_guests", sa.Integer(), nullable=False),
        sa.Column("max_guests", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("min_guests >= 1 AND max_guests >= min_guests", name="ck_tier_guests"),
        schema="catalog",
    )
    op.create_table(
        "ticket_prices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tier_id", sa.Uuid(), sa.ForeignKey("catalog.ticket_tiers.id"), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_minor > 0", name="ck_price_positive"),
        sa.CheckConstraint("version > 0", name="ck_price_version"),
        sa.UniqueConstraint("tier_id", "version", name="uq_tier_price_version"),
        schema="catalog",
    )
    op.create_index("ix_catalog_ticket_prices_tier_id", "ticket_prices", ["tier_id"], schema="catalog")
    op.create_index(
        "uq_one_active_price_per_tier", "ticket_prices", ["tier_id"],
        unique=True, schema="catalog", postgresql_where=sa.text("active = true"),
    )


def downgrade():
    op.drop_table("ticket_prices", schema="catalog")
    op.drop_table("ticket_tiers", schema="catalog")
    op.drop_table("attractions", schema="catalog")

