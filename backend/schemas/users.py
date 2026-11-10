from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    login: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: str = Field(min_length=1)


class UserUpdate(BaseModel):
    login: str = Field(min_length=1)
    role: str = Field(min_length=1)
    password: str | None = None


class UserOut(BaseModel):
    id: int
    login: str
    role: str
