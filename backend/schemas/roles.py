from pydantic import BaseModel
from typing import Dict, List

class RoleSchema(BaseModel):
    name: str
    permissions: List[str]

class RolePermissions(BaseModel):
    permissions: list[str]
