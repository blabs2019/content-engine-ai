from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Boolean, DateTime, Integer, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vertical(Base):
    __tablename__ = "verticals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    content_type_weights: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content_types_enabled: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    seasons: Mapped[list["VerticalSeason"]] = relationship(back_populates="vertical", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'trigger_type': self.trigger_type, 'is_active': self.is_active,
            'content_type_weights': self.content_type_weights or {},
            'content_types_enabled': self.content_types_enabled or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class VerticalSeason(Base):
    __tablename__ = "vertical_seasons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vertical_id: Mapped[int] = mapped_column(ForeignKey("verticals.id", ondelete="CASCADE"), nullable=False)
    season_window: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    month_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    month_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    focus: Mapped[str] = mapped_column(String(255), nullable=False)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_post: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    vertical: Mapped["Vertical"] = relationship(back_populates="seasons")

    def is_active_for_month(self, month: int) -> bool:
        if not self.active:
            return False
        if self.month_start is None or self.month_end is None:
            return True
        if self.month_start <= self.month_end:
            return self.month_start <= month <= self.month_end
        else:
            return month >= self.month_start or month <= self.month_end

    def to_dict(self):
        return {
            'id': self.id, 'vertical_id': self.vertical_id,
            'season_window': self.season_window,
            'trigger_system': self.trigger_system,
            'month_start': self.month_start, 'month_end': self.month_end,
            'focus': self.focus, 'hook': self.hook,
            'example_post': self.example_post,
            'priority': self.priority, 'active': self.active,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
