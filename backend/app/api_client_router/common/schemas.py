"""對外 API Client 端點的請求 schema(憑證一律走 body,禁 query / header 帶密)。"""

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    """`POST /token`:Client Credentials 換發短效 JWT。"""

    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)


class RefreshTokenRequest(TokenRequest):
    """`POST /refresh_token`:另帶待刷新的舊 access_token(過期亦可,驗簽章與 sub)。"""

    access_token: str = Field(min_length=1)
