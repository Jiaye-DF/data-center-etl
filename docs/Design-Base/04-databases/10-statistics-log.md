# 10-statistics-log — 請求統計 log(選用)

> **何時讀**:評估要不要加 / 加了之後 register middleware 才讀。

---

## 一句話判定

**有 Redis → 加;沒 Redis → 不加。**(沒 Redis 就硬上 = 同步寫 DB 拖慢每個 request,得不償失)

「沒 Redis」=  專案沒佈 Redis service / 不打算為了 log 加。POC、純內部工具通常落這格。

---

## 使用者只要做 3 件事

> 套件 `df-statistics-log` **尚未實作**,本檔是給未來實作的契約。屆時專案這樣用:

```python
# main.py
from df_statistics_log import StatisticsLogMiddleware

app.add_middleware(
    StatisticsLogMiddleware,
    project_name="df_recycle",                      # 1. table prefix
    redis_url=settings.REDIS_URL,                   # 2. queue 用
    exclude_paths={"/api/v1/health", "/api/docs"},  # 3. 不想記的路徑
)
```

完。Schema、redact、partition、保留期 — 套件處理。

- table 名稱:套件自動建 `<project_name>_statistics_log`
- migration:套件 alembic chain 串進專案,**禁**手寫 model
- 保留期:預設 90 天;HR / 財務類專案需更長 → 在 `docs/Tasks/v1.0.0/propose.md` 註明 + 套件參數覆寫

## 不採用時

- **禁**手刻替代品(寫個 file log / print 不算 — 沒 redact、沒 partition、沒索引)
- 真要 log → 補 Redis(對齊 `06-Coolify-CD/01-compose.md`),走套件
- 要查問題 → 走 application log(`03-backend/05-exceptions-and-logging.md`)+ `request_id`

---

## 套件契約(實作此套件時讀)

> 一般開發者**不用**讀以下。給未來開 `df-statistics-log` repo 的人。

### Table schema

```python
class StatisticsLog(Base):
    __tablename__ = f"{project_name}_statistics_log"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True, default=uuid4)

    user_uid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    ip_address: Mapped[str] = mapped_column(INET, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)             # 路由模板,不展開 UID
    query_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
```

- append-only,**不**繼承 `BaseModel`(無 `is_deleted` / `created_by` / `updated_by` / `updated_at`)
- 每欄**必** `COMMENT ON COLUMN` 中英雙語(對齊 `00-overview.md`)

### 寫入流程

1. middleware 攔截 request → 組 record → push Redis list
2. worker 從 Redis 批次寫入 PG
3. middleware 失敗 / Redis 失敗 **不**得讓主 request fail → 丟 application logger

### Redact(寫 Redis 前)

| 來源 | 規則 |
| --- | --- |
| `request_body` / `query_params` 內 key 含 `password` / `token` / `secret` / `api_key` / `authorization` / `cookie`(case-insensitive) | 值改 `"***REDACTED***"` |
| `request_body` > 10 KB | 截斷 + `_truncated: true` |
| multipart 檔案上傳 | 只記 filename + size,**禁**寫內容 |
| response body | **完全不記**(走 application log + `request_id` 對應) |

### Index(必建 4 條)

```sql
CREATE INDEX idx_<project>_statistics_log_user_uid_created_at  ON ... (user_uid, created_at DESC);
CREATE INDEX idx_<project>_statistics_log_path_created_at      ON ... (path, created_at DESC);
CREATE INDEX idx_<project>_statistics_log_status_code_created  ON ... (status_code, created_at DESC);
CREATE INDEX idx_<project>_statistics_log_request_id           ON ... (request_id);
```

### 分區 + 保留

- 按月 RANGE partition `created_at`(GET 也記,單表會破億行,沒 partition 之後 vacuum 會死)
- 預設保留 90 天;超過走 `DETACH PARTITION` → 落冷儲存(S3 / GCS)→ DROP

---

## 跨領域對應

- 軟刪除豁免 → `00-overview.md § 軟刪除原則`
- 敏感欄位 redact → `03-passwords-and-pii.md`(套件遵循,不用每專案重寫)
- 應用級 logging → `03-backend/05-exceptions-and-logging.md`(共用 `request_id` 串接)
- Redis 服務佈建 → `06-Coolify-CD/01-compose.md`
