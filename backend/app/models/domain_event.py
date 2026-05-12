import json

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class DomainEventRecord(Base):
    __tablename__ = "domain_events"

    event_id = Column(String(36), primary_key=True)
    trace_id = Column(String(36), nullable=False, index=True)
    event_name = Column(String(64), nullable=False, index=True)
    user_id = Column(UnsignedInt, nullable=False, index=True)
    payload = Column(Text, nullable=False, server_default="{}")
    occurred_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    @property
    def payload_json(self) -> dict:
        if not self.payload:
            return {}
        try:
            loaded = json.loads(self.payload)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

