from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class MemoryEmbedding(Base):
    __tablename__ = "memory_embedding"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(
        UnsignedInt,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slice_id = Column(
        UnsignedInt,
        ForeignKey("ukl_slice.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    model = Column(String(64), nullable=False)
    dimensions = Column(UnsignedInt, nullable=False)
    embedding_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
