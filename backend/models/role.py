from sqlalchemy import Column, String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from models.base import Base
from models.permission import role_permissions, Permission

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        backref="roles"
    )
