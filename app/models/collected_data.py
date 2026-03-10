from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Float, ForeignKey, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CollectedData(Base):
    __tablename__ = "collected_data"
    __table_args__ = (
        Index("ix_collected_data_source", "source"),
        Index("ix_collected_data_vertical_id", "vertical_id"),
        Index("ix_collected_data_collected_at", "collected_at"),
        Index("ix_collected_data_trending", "is_trending"),
        Index("ix_collected_data_vertical_source_trending", "vertical_id", "source", "is_trending"),
        Index("ix_collected_data_source_id_unique", "source", "source_id", unique=True),
        Index("ix_collected_data_all_time_favourite", "is_all_time_favourite"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vertical_id: Mapped[int] = mapped_column(ForeignKey("verticals.id", ondelete="CASCADE"), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    file_urls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(100), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reach_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_trending: Mapped[bool] = mapped_column(Boolean, default=False)
    is_all_time_favourite: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    vertical: Mapped["Vertical"] = relationship()
