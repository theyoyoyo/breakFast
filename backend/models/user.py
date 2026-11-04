from pydantic import BaseModel, Field


class UserLogin(BaseModel):
    # Loose caps, so junk is refused before it is hashed or kept in the failed-login counts.
    # PINs set before the 6-10 digit rule could be any length, so login takes up to 64.
    name: str = Field(max_length=100)
    pin: str = Field(max_length=64)


class UserOut(BaseModel):
    id: int
    name: str
    is_admin: int
    created_at: str


class TokenOut(BaseModel):
    token: str
    user: UserOut
