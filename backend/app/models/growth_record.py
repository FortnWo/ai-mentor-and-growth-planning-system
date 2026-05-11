from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class GrowthRecordType(str, Enum):
    MANUAL = "manual"
    ACTION_PLAN = "action_plan"
    MILESTONE = "milestone"


class GrowthRecordSource(str, Enum):
    MANUAL = "manual"
    ACTION_PLAN = "action_plan"
    MILESTONE = "milestone"


class GrowthRecord(Base):
    __tablename__ = "growth_records"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(UnsignedInt, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)

    record_type = Column(
        SQLEnum(GrowthRecordType, values_callable=lambda values: [v.value for v in values], native_enum=False),
        nullable=False,
        server_default=f"'{GrowthRecordType.MANUAL.value}'",
    )

    source_type = Column(
        SQLEnum(GrowthRecordSource, values_callable=lambda values: [v.value for v in values], native_enum=False),
        nullable=False,
        server_default=f"'{GrowthRecordSource.MANUAL.value}'",
    )
    source_ref_id = Column(UnsignedInt, nullable=True, index=True)

    occurred_at = Column(DateTime, nullable=True, index=True)
    record_date = Column(String(10), nullable=True, index=True)

    emotion = Column(String(64), nullable=True)
    score = Column(Integer, nullable=True)

    idempotency_key = Column(String(128), nullable=True, index=True)
    ai_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)
