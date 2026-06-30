# 03-async-and-tx — async safety + transaction

> **何時讀**:寫 service 跨表 / hash / 阻塞操作才讀。

## async safety:CPU-bound 必 thread offload

async 函式內**禁**裸呼叫 ≥ 50 ms 同步 CPU 操作(bcrypt / argon2 / 大 JSON parse / 影像處理)。**必** `await asyncio.to_thread(fn, *args)`。`core/security.py` **同時**提供同步 + `*_async` 兩版。

```python
ok = await asyncio.to_thread(verify_password, plain, hashed)  # ✅
ok = verify_password(plain, hashed)                            # ❌ 卡 event loop
```

## Service 多表寫入必 transaction

Service 內 ≥ 2 處跨**不同表**寫入 → **必** `async with self.db.begin():`(或 `begin_nested()` 若 caller 已包 begin)。transaction 內**禁**含長阻塞操作;hash 須在 begin 之前算完。

```python
secret_hash = await hash_password_async(payload.secret_plain)  # 先做完
async with self.db.begin():
    user = User(...); self.db.add(user); await self.db.flush()
    cred = UserMockCredential(user_uid=user.uid, secret_hash=secret_hash); self.db.add(cred)
```
