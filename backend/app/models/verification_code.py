from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from app.core.database import Base

UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(UnsignedInt, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(SQLEnum("phone", "email", name="vc_type"), nullable=False)
    code = Column(String(16), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
