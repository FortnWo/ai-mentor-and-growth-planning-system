from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class UklSlice(Base):
    __tablename__ = "ukl_slice"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(
        UnsignedInt,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slice_type = Column(String(64), nullable=False, index=True)
    source_module = Column(String(64), nullable=False)
    ref_type = Column(String(32), nullable=True)
    ref_id = Column(UnsignedInt, nullable=True, index=True)
    payload = Column(Text, nullable=False)
    version = Column(UnsignedInt, nullable=False, server_default="1")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
