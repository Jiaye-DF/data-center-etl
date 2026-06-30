# 01-identifiers — 對外 vs 對內識別碼

> **何時讀**:設計新表才讀。

- 內部主鍵僅供 DB 內部關聯;**禁**暴露於 API / 前端
- 對外一律 UUID;FastAPI 路徑用 UID
- 外部系統 ID(Azure AD `oid` / Stripe `customer.id`)以**獨立欄位**儲存(`azure_ad_object_id UUID`),**禁**作為主鍵或對外 UID
