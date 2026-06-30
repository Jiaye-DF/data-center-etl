# 02-soft-delete — Repository 命名強制

> **何時讀**:寫 Repository 才讀。

- **預設過濾版**(過濾 `is_deleted`):無後綴 — `find_by_uid` / `get_*` / `list_*`
- **不過濾版**(包含已軟刪)**必**加 `_including_deleted` 後綴
- **禁**反向命名(把過濾版叫 `find_active_*` 而把不過濾版佔用 `find_*`)

```python
async def find_by_uid(self, uid):                    # ✅ 預設過濾
async def find_by_uid_including_deleted(self, uid):  # ✅ 明確不過濾
async def find_active_by_uid(self, uid):             # ✅ 過濾 deleted + is_active=FALSE
```
