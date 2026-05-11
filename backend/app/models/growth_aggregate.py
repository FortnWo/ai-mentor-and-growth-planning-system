from sqlalchemy import Column, Date, DateTime, Integer, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class GrowthDailyAggregate(Base):
    __tablename__ = "growth_daily_aggregates"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(UnsignedInt, nullable=False, index=True)
    record_date = Column(Date, nullable=False, index=True)

    completed_count = Column(Integer, nullable=False, server_default="0")
    reflection_count = Column(Integer, nullable=False, server_default="0")
    milestone_count = Column(Integer, nullable=False, server_default="0")
    growth_score = Column(Integer, nullable=False, server_default="0")

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
