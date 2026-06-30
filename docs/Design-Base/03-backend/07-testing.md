# 07-testing — 後端測試

> **何時讀**:寫測試才讀。

- DB 整合測試**禁** mock SQL,須真實測試 DB(`pytest-asyncio` + alembic 跑 schema)
- 第三方:`respx` / `httpx.MockTransport`
- 測試檔案結構**對映** `app/`
