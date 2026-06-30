# 03-passwords-and-pii — 密碼 / PII

> **何時讀**:處理使用者資料 / PII 才讀。

- 密碼**必** `passlib[bcrypt]` 或 argon2;**禁** md5 / sha1 / 明文
- bcrypt 在 async 上下文**必** `asyncio.to_thread` 包裝(`03-backend/03-async-and-tx.md`)
- 不可逆雜湊欄位(BCrypt hash 等)應與 PII 隔離(獨立 credential 表)
- PII 欄位 schema 加 `comment="PII"` 或 `-- PII`
