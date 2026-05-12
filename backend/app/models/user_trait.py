import json

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import relationship

from app.core.database import Base


UnsignedInt = Integer().with_variant(MYSQL_INTEGER(unsigned=True), "mysql")


class UserTrait(Base):
    __tablename__ = "user_traits"
    __table_args__ = (
        UniqueConstraint("user_id", "trait_type", "trait_key", name="uq_user_traits_user_type_key"),
    )

    id = Column(UnsignedInt, primary_key=True, index=True)
    user_id = Column(UnsignedInt, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trait_type = Column(String(64), nullable=False, index=True)
    trait_key = Column(String(255), nullable=False, index=True)
    trait_value = Column(Text, nullable=True)
    trait_score = Column(Float, nullable=False, server_default="1")
    source = Column(String(64), nullable=False, server_default="ai")
    confidence = Column(Float, nullable=True)
    last_observed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="traits")

    @property
    def value_json(self) -> dict:
        if not self.trait_value:
            return {}
        try:
            loaded = json.loads(self.trait_value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

