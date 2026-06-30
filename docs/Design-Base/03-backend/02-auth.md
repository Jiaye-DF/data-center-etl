# 02-auth — 認證 + CORS

> **何時讀**:寫保護 endpoint / 登入 / CORS 配置才讀。

## 認證與授權

- 登入 JWT 透過 `set_cookie(httponly=True, secure=True, samesite="lax")` 設定
- 權限檢查**集中**於 `api/deps.py`:`Depends(require_role(...))` / `Depends(require_permission(...))`
- **禁**各 router 自行解析 cookie

## CORS

```python
app.add_middleware(CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # 從 env 讀,禁 ["*"]
    allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])
```

**禁** `allow_credentials=True` + `allow_origins=["*"]` 同時。
