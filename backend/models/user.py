from sqlalchemy import Column, String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(ForeignKey("roles.id"))
    role = relationship("Role")

    @property
    def permissions(self) -> set[str]:
        if not self.role:
            return set()
        return {p.name for p in self.role.permissions}
