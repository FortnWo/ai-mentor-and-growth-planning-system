from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import relationship

from app.core.database import Base


class ActionPlanStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    FAILED = "failed"


class ActionPlanFrequency(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class ActionPlan(Base):
    __tablename__ = "action_plans"
    __table_args__ = (UniqueConstraint("goal_id", "main_breakdown_id", name="uq_action_plan_goal_main_breakdown"),)

    id = Column(UnsignedInt, primary_key=True, index=True)
    goal_id = Column(
        UnsignedInt,
        ForeignKey("goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    main_breakdown_id = Column(
        UnsignedInt,
        ForeignKey("goal_breakdowns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    status = Column(
        SQLEnum(
            ActionPlanStatus,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
        ),
        nullable=False,
        server_default=text("'pending'"),
    )
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    goal = relationship("Goal", back_populates="action_plans")
    items = relationship(
        "ActionPlanItem",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ActionPlanItem.sequence",
    )


class ActionPlanItem(Base):
    __tablename__ = "action_plan_items"

    id = Column(UnsignedInt, primary_key=True, index=True)
    plan_id = Column(UnsignedInt, ForeignKey("action_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    breakdown_id = Column(
        UnsignedInt,
        ForeignKey("goal_breakdowns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(
        SQLEnum(
            ActionPlanFrequency,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
        ),
        nullable=False,
        server_default=text("'custom'"),
    )
    schedule = Column(Text, nullable=True)
    status = Column(
        SQLEnum(
            ActionPlanStatus,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
        ),
        nullable=False,
        server_default=text("'pending'"),
    )
    start_date = Column(String(10), nullable=True)
    due_date = Column(String(10), nullable=True)
    sequence = Column(Integer, nullable=False, server_default=text("0"))

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    plan = relationship("ActionPlan", back_populates="items")
    breakdown = relationship("GoalBreakdown")