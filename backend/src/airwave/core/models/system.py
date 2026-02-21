"""System models: SystemSetting."""

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from airwave.core.models.base import Base, TimestampMixin


class SystemSetting(Base, TimestampMixin):
    """Persistent storage for dynamic application settings."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
