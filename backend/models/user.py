from pydantic import BaseModel


class UserLogin(BaseModel):
    name: str
    pin: str


class UserOut(BaseModel):
    id: int
    name: str
    is_admin: int
    created_at: str


class TokenOut(BaseModel):
    token: str
    user: UserOut
