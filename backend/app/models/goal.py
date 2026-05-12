from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import relationship

from app.core.database import Base


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class GoalPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GoalBreakdownStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class Goal(Base):
    __tablename__ = "user_goals"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(UnsignedInt, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        SQLEnum(
            GoalStatus,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
        ),
        nullable=False,
        server_default=text("'active'"),
    )
    priority = Column(
        SQLEnum(
            GoalPriority,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
        ),
        nullable=False,
        server_default=text("'medium'"),
    )
    target_date = Column(String(10), nullable=True)  # ISO 8601 date format: YYYY-MM-DD

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="goals")
    breakdowns = relationship("GoalBreakdown", back_populates="goal", cascade="all, delete-orphan")
    action_plan = relationship("ActionPlan", back_populates="goal", uselist=False, cascade="all, delete-orphan")


class GoalBreakdown(Base):
    __tablename__ = "goal_breakdowns"

    id = Column(UnsignedInt, primary_key=True, index=True)
    goal_id = Column(UnsignedInt, ForeignKey("user_goals.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(UnsignedInt, ForeignKey("goal_breakdowns.id", ondelete="CASCADE"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    level = Column(Integer, nullable=False, server_default=text("0"))
    sequence = Column(Integer, nullable=False, server_default=text("0"))

    status = Column(
        SQLEnum(
            GoalBreakdownStatus,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
        ),
        nullable=False,
        server_default=text("'pending'"),
    )
    due_date = Column(String(10), nullable=True)  # ISO 8601 date format: YYYY-MM-DD

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    goal = relationship("Goal", back_populates="breakdowns")
    children = relationship("GoalBreakdown", remote_side=[parent_id], cascade="all, delete-orphan")
