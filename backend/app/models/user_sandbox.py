"""
User Sandbox Model
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.auth import AuthUser  # pragma: no cover


class UserSandbox(Base, TimestampMixin):
    """
    用户沙箱记录表

    存储用户的个人沙箱实例信息，包括容器ID、状态、资源限制等。
    每个用户同一时间只能有一个活跃沙箱记录。
    """

    __tablename__ = "user_sandbox"

    # 沙箱 ID (通常与 user_id 关联，或者是独立的 UUID)
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # 关联用户
    user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Docker 容器信息
    container_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 状态: pending, creating, running, stopped, failed, terminating
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # 镜像和运行时配置
    image: Mapped[str] = mapped_column(String(255), default="python:3.12-slim", nullable=False)
    runtime: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 运行状态跟踪
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 资源限制配置
    cpu_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # CPU 核心数，如 1.0
    memory_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 内存大小 (MB)，如 512
    idle_timeout: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)  # 闲置超时 (秒)

    # 关系
    user: Mapped["AuthUser"] = relationship("AuthUser", back_populates="sandbox")
