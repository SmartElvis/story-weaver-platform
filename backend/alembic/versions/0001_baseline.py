"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-26 00:00:00.000000

Initial schema for the Story platform. This mirrors what
``Base.metadata.create_all`` previously produced (users, projects, chapters,
style_profiles, plot_chunks, style_chunks) plus their secondary, HNSW vector,
and GIN full-text indexes.

Note for existing databases: if your tables were already created by
``create_all``, either start from a fresh database or run
``alembic stamp 0001_baseline`` to mark this baseline as applied without
re-running it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("salt", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("llm_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )

    # --- style_profiles ---
    op.create_table(
        "style_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_books", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_chunks", sa.Integer(), nullable=True),
        sa.Column("style_features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("processing_status", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_style_profiles_owner_id", "style_profiles", ["owner_id"])

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("genre", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("outline", sa.Text(), nullable=True),
        sa.Column("character_cards", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("world_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("active_style_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("writing_preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("style_controls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["active_style_id"], ["style_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_active_style_id", "projects", ["active_style_id"])
    op.create_index(
        "ix_projects_owner_updated",
        "projects",
        ["owner_id", sa.text("updated_at DESC")],
    )

    # --- chapters ---
    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("draft_content", sa.Text(), nullable=True),
        sa.Column("final_content", sa.Text(), nullable=True),
        sa.Column("logic_review", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("style_review", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extraction_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("next_chapter_suggestion", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("revision_count", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("generation_cost", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chapters_project_number", "chapters", ["project_id", "chapter_number"])

    # --- plot_chunks ---
    op.create_table(
        "plot_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("scene_type", sa.String(length=50), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("tokens", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plot_chunks_chapter_id", "plot_chunks", ["chapter_id"])
    op.create_index("ix_plot_chunks_project_id", "plot_chunks", ["project_id"])
    op.create_index(
        "ix_plot_chunks_embedding_hnsw",
        "plot_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_plot_chunks_tokens_gin",
        "plot_chunks",
        [sa.text("to_tsvector('simple', coalesce(tokens, ''))")],
        postgresql_using="gin",
    )

    # --- style_chunks ---
    op.create_table(
        "style_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("style_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_book", sa.String(length=255), nullable=True),
        sa.Column("chapter_source", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("tokens", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.ForeignKeyConstraint(["style_profile_id"], ["style_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_style_chunks_style_profile_id", "style_chunks", ["style_profile_id"])
    op.create_index(
        "ix_style_chunks_embedding_hnsw",
        "style_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_style_chunks_tokens_gin",
        "style_chunks",
        [sa.text("to_tsvector('simple', coalesce(tokens, ''))")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_style_chunks_tokens_gin", table_name="style_chunks")
    op.drop_index("ix_style_chunks_embedding_hnsw", table_name="style_chunks")
    op.drop_index("ix_style_chunks_style_profile_id", table_name="style_chunks")
    op.drop_table("style_chunks")

    op.drop_index("ix_plot_chunks_tokens_gin", table_name="plot_chunks")
    op.drop_index("ix_plot_chunks_embedding_hnsw", table_name="plot_chunks")
    op.drop_index("ix_plot_chunks_project_id", table_name="plot_chunks")
    op.drop_index("ix_plot_chunks_chapter_id", table_name="plot_chunks")
    op.drop_table("plot_chunks")

    op.drop_index("ix_chapters_project_number", table_name="chapters")
    op.drop_table("chapters")

    op.drop_index("ix_projects_owner_updated", table_name="projects")
    op.drop_index("ix_projects_active_style_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_style_profiles_owner_id", table_name="style_profiles")
    op.drop_table("style_profiles")

    op.drop_table("users")
