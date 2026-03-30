from pydantic import BaseModel
from datetime import datetime


class APResponse(BaseModel):
    id: int
    mac: str
    quarto: str
    foto_path: str | None = None
    data_registo: datetime

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    results: list[APResponse]


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"