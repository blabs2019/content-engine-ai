from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vertical(Base):
    __tablename__ = "verticals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    seasons: Mapped[list["VerticalSeason"]] = relationship(back_populates="vertical", cascade="all, delete-orphan", lazy="selectin")


class VerticalSeason(Base):
    __tablename__ = "vertical_seasons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vertical_id: Mapped[int] = mapped_column(ForeignKey("verticals.id", ondelete="CASCADE"), nullable=False)
    season_window: Mapped[str] = mapped_column(String(50), nullable=False)
    focus: Mapped[str] = mapped_column(String(255), nullable=False)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_post: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    vertical: Mapped["Vertical"] = relationship(back_populates="seasons")
