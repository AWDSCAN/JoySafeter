"""
执行追踪模型

参考 Langfuse Trace / Observation 模型，用于持久化 LangGraph 执行数据。
支持层级 observation 关系（parent_observation_id -> self）。
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


# ============ Enums ============


class TraceStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class ObservationType(str, enum.Enum):
    SPAN = "SPAN"  # Node execution (wraps children)
    GENERATION = "GENERATION"  # LLM call
    TOOL = "TOOL"  # Tool invocation
    EVENT = "EVENT"  # Singular events (thoughts, logs)


class ObservationLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    DEFAULT = "DEFAULT"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ObservationStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


# ============ ExecutionTrace ============


class ExecutionTrace(Base):
    """
    执行追踪表 — 对应一次完整的 Graph 执行。
    类似 Langfuse 的 Trace。
    """

    __tablename__ = "execution_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 关联
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True, comment="工作空间 ID"
    )
    graph_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True, comment="Graph ID"
    )
    thread_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True, comment="对话线程 ID")
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True, comment="用户 ID")

    # 基本信息
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Graph / Trace 名称")
    status: Mapped[TraceStatus] = mapped_column(
        Enum(TraceStatus), default=TraceStatus.RUNNING, nullable=False, comment="执行状态"
    )

    # 输入输出
    input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="执行输入")
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="执行输出")

    # 时间
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, comment="开始时间"
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="结束时间")
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="执行时长(毫秒)")

    # Token / Cost 聚合
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="总 token 数")
    total_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="总费用")

    # 元数据
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True, comment="自定义元数据 (tags, etc.)"
    )
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="标签列表")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), onupdate=utc_now, nullable=False
    )

    # 关系
    observations: Mapped[list["ExecutionObservation"]] = relationship(
        "ExecutionObservation",
        back_populates="trace",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_execution_traces_graph_thread", "graph_id", "thread_id"),
        Index("ix_execution_traces_start_time", "start_time"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionTrace(id={self.id}, name={self.name}, status={self.status})>"


# ============ ExecutionObservation ============


class ExecutionObservation(Base):
    """
    执行观测表 — 对应一个 Observation (Span / Generation / Tool / Event)。
    通过 parent_observation_id 支持 N 层嵌套。
    类似 Langfuse 的 Observation。
    """

    __tablename__ = "execution_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 关联
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("execution_traces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联的 Trace ID",
    )
    parent_observation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("execution_observations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="父 Observation ID (实现层级嵌套)",
    )

    # 类型与标识
    type: Mapped[ObservationType] = mapped_column(Enum(ObservationType), nullable=False, comment="观测类型")
    name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="名称 (node name, tool name, model name)"
    )
    level: Mapped[ObservationLevel] = mapped_column(
        Enum(ObservationLevel), default=ObservationLevel.DEFAULT, nullable=False, comment="日志级别"
    )
    status: Mapped[ObservationStatus] = mapped_column(
        Enum(ObservationStatus), default=ObservationStatus.RUNNING, nullable=False, comment="执行状态"
    )
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="状态信息 / 错误信息")

    # 时间
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, comment="开始时间"
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="结束时间")
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="执行时长(毫秒)")
    completion_start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="首 token 时间 (GENERATION)"
    )

    # 输入输出
    input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="输入数据")
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="输出数据")

    # 模型信息 (GENERATION type)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="模型名称")
    model_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="模型提供商")
    model_parameters: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="模型参数 (temperature, etc.)"
    )

    # Token 使用
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="输入 token 数")
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="输出 token 数")
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="总 token 数")

    # 费用
    input_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="输入费用")
    output_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="输出费用")
    total_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="总费用")

    # 元数据
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True, comment="自定义元数据")
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="代码/模型版本")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )

    # 关系
    trace: Mapped["ExecutionTrace"] = relationship("ExecutionTrace", back_populates="observations")
    children: Mapped[list["ExecutionObservation"]] = relationship(
        "ExecutionObservation",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="noload",
    )
    parent: Mapped[Optional["ExecutionObservation"]] = relationship(
        "ExecutionObservation",
        back_populates="children",
        remote_side=[id],
        lazy="noload",
    )

    __table_args__ = (
        Index("ix_execution_observations_trace_start", "trace_id", "start_time"),
        Index("ix_execution_observations_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionObservation(id={self.id}, type={self.type}, name={self.name})>"
