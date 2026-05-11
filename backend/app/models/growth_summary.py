from sqlalchemy import Column, Date, DateTime, Integer, Text, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class GrowthSummary(Base):
    __tablename__ = "growth_summaries"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(UnsignedInt, nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
