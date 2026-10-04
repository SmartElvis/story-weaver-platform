import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    outline: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_cards: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    world_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    active_style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("style_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    writing_preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    style_controls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    arc_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="projects")
    chapters = relationship(
        "Chapter", back_populates="project", lazy="selectin", cascade="all, delete-orphan"
    )
    active_style = relationship("StyleProfile", foreign_keys=[active_style_id])
    plot_chunks = relationship(
        "PlotChunk", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Optimizes "list my projects ordered by most recently updated"
        Index("ix_projects_owner_updated", owner_id, updated_at.desc()),
    )
