import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, Integer, Index, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlotChunk(Base):
    __tablename__ = "plot_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scene_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(1024), nullable=True)

    # Relationships
    chapter = relationship("Chapter", back_populates="plot_chunks")
    project = relationship("Project", back_populates="plot_chunks")

    __table_args__ = (
        Index(
            "ix_plot_chunks_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_plot_chunks_tokens_gin",
            text("to_tsvector('simple', coalesce(tokens, ''))"),
            postgresql_using="gin",
        ),
    )


class StyleChunk(Base):
    __tablename__ = "style_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    style_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("style_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_book: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chapter_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(1024), nullable=True)

    # Relationships
    style_profile = relationship("StyleProfile", back_populates="style_chunks")

    __table_args__ = (
        Index(
            "ix_style_chunks_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_style_chunks_tokens_gin",
            text("to_tsvector('simple', coalesce(tokens, ''))"),
            postgresql_using="gin",
        ),
    )
