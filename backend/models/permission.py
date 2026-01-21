from sqlalchemy import Column, String, Integer, ForeignKey, Table
from sqlalchemy.orm import relationship
from .base import Base

# Many-to-many Role <-> Permission
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id"), primary_key=True),
)

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
