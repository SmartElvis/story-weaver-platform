import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OUTLINE"
    )  # OUTLINE / DRAFTING / REVIEW / REVISION / FINALIZED
    direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    logic_review: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    style_review: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    next_chapter_suggestion: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    generation_cost: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project = relationship("Project", back_populates="chapters")
    plot_chunks = relationship(
        "PlotChunk", back_populates="chapter", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Serves listing chapters of a project ordered by chapter_number and
        # the workflow's "previous chapters" lookup (project_id + chapter_number range).
        Index("ix_chapters_project_number", project_id, chapter_number),
    )
