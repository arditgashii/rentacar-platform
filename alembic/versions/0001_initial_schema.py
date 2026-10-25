"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-25 02:26:40.746370
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)

    op.create_table(
        "cars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("make", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=60), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("transmission", sa.String(length=20), nullable=False),
        sa.Column("fuel_type", sa.String(length=20), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("doors", sa.Integer(), nullable=False),
        sa.Column("mileage_km", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=40), nullable=False),
        sa.Column("license_plate", sa.String(length=20), nullable=False),
        sa.Column("daily_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("deposit", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("pickup_address", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("license_plate"),
    )
    with op.batch_alter_table("cars", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cars_category"), ["category"], unique=False)
        batch_op.create_index(batch_op.f("ix_cars_city"), ["city"], unique=False)
        batch_op.create_index(batch_op.f("ix_cars_daily_price"), ["daily_price"], unique=False)
        batch_op.create_index(batch_op.f("ix_cars_owner_id"), ["owner_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_cars_status"), ["status"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notifications_user_id"), ["user_id"], unique=False)

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("car_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["car_id"], ["cars.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_bookings_car_id"), ["car_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_bookings_client_id"), ["client_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_bookings_status"), ["status"], unique=False)

    op.create_table(
        "car_photos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("car_id", sa.Integer(), nullable=False),
        sa.Column("blob_name", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["car_id"], ["cars.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blob_name"),
    )
    with op.batch_alter_table("car_photos", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_car_photos_car_id"), ["car_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("car_photos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_car_photos_car_id"))

    op.drop_table("car_photos")
    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_bookings_status"))
        batch_op.drop_index(batch_op.f("ix_bookings_client_id"))
        batch_op.drop_index(batch_op.f("ix_bookings_car_id"))

    op.drop_table("bookings")
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_notifications_user_id"))

    op.drop_table("notifications")
    with op.batch_alter_table("cars", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cars_status"))
        batch_op.drop_index(batch_op.f("ix_cars_owner_id"))
        batch_op.drop_index(batch_op.f("ix_cars_daily_price"))
        batch_op.drop_index(batch_op.f("ix_cars_city"))
        batch_op.drop_index(batch_op.f("ix_cars_category"))

    op.drop_table("cars")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_email"))

    op.drop_table("users")
