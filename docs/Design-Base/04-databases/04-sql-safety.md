# 04-sql-safety — SQL 安全

> **何時讀**:寫 raw SQL 才讀。

**禁**字串拼接 / f-string 拼 SQL → 用 SQLAlchemy ORM;raw SQL 用 `text(...).bindparams(...)`。

```python
text(f"SELECT * FROM users WHERE id = {user_id}")            # ❌ injection
text("SELECT * FROM users WHERE id = :id").bindparams(id=user_id)  # ✅
```
