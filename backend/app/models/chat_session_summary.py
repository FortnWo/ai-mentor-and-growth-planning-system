from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class ChatSessionSummary(Base):
    __tablename__ = "chat_session_summary"

    id = Column(UnsignedInt, primary_key=True, index=True)
    session_id = Column(
        UnsignedInt,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(
        UnsignedInt,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary = Column(Text, nullable=False)
    summarized_through_message_id = Column(UnsignedInt, nullable=True)
    message_count = Column(UnsignedInt, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
