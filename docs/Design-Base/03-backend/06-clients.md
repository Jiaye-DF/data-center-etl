# 06-clients — 第三方 client

> **何時讀**:串第三方才讀(細節見 `90-third-party-service/`)。

集中於 `app/clients/`,依服務分子目錄。用 `httpx.AsyncClient`(於 lifespan 建立)。client 須處理 timeout / retry / 錯誤轉 `AppError`。**禁**在 services / api 直 `httpx.get(...)`。

詳細各服務範本(SMTP / SSO / payment / monitoring 等)見 `90-third-party-service/`。
