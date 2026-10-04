import uuid

from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_books: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    style_features: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    owner = relationship("User", back_populates="style_profiles")
    style_chunks = relationship(
        "StyleChunk", back_populates="style_profile", cascade="all, delete-orphan"
    )
