from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base

UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(UnsignedInt, primary_key=True, index=True)
    key = Column(String(128), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(UnsignedInt, nullable=True, index=True)
    model = Column(String(128), nullable=False)
    prompt_tokens = Column(UnsignedInt, nullable=False, default=0)
    completion_tokens = Column(UnsignedInt, nullable=False, default=0)
    task = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
