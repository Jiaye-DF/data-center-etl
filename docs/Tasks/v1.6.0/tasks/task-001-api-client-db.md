---
id: task-001
title: api_client_users + api_client_secrets 資料表(models + migration + repository)
status: done
worker: worker-A
parallel: true
depends_on: []
affected_files:
  - backend/app/models/api_client_user.py
  - backend/app/models/api_client_secret.py
  - backend/app/models/__init__.py
  - backend/alembic/versions/v8_add_api_client_users.py
  - backend/app/repositories/api_client_repo.py
  - backend/tests/test_api_client_models_repo.py
estimated_hours: 3
---

## 目標

建立 API Client 機器身分的 DB 地基:`api_client_users` 主表 + `api_client_secrets` 子表(雙鑰輪替),與後台既有 `users` / roles 完全分離;含 Alembic migration 與 Repository。

## 規格(user 已確認,不再問)

**`api_client_users`**(繼承 `BaseModel`,見 `backend/app/models/base.py`):

| 欄位 | 型別 | 約束 / 預設 |
| --- | --- | --- |
| `client_id` | `String(100)` NOT NULL | 取 token 識別;partial unique index `uq_api_client_users_client_id`(`is_deleted = false`,比照 `uq_users_username`) |
| `name` | `String(255)` NOT NULL | 應用系統名稱 |
| `description` | `Text` NULL | 用途說明 |
| `status` | `String(20)` NOT NULL default `enabled` | CHECK `status IN ('enabled','disabled')`,命名 `ck_api_client_users_status` |
| `rate_limit_per_minute` | `Integer` NOT NULL default `30` | 每分鐘請求上限 |
| `rate_limit_per_10min` | `Integer` NOT NULL default `200` | 每 10 分鐘請求上限 |

**`api_client_secrets`**(繼承 `BaseModel`):

| 欄位 | 型別 | 約束 / 預設 |
| --- | --- | --- |
| `api_client_user_pid` | `BigInteger` FK → `api_client_users.pid` NOT NULL | `fk_api_client_secrets_api_client_user` + index `idx_api_client_secrets_api_client_user_pid` |
| `secret_hash` | `Text` NOT NULL | 只存 bcrypt 雜湊(比照 `users.password_hash`) |
| `status` | `String(20)` NOT NULL default `active` | CHECK `status IN ('active','retired')`,命名 `ck_api_client_secrets_status` |

- 每欄 `comment=` 中英雙語(比照 `user.py`)。
- Repository `api_client_repo.py`:`get_by_client_id`(過濾 `is_deleted == False`、僅回傳含 active secrets 所需資料)、`list_`、`create`、`update`、`add_secret`、`retire_secret`;軟刪除規範命名(見 `02-soft-delete.md`)。「同 Client active secret ≤ 2」為應用層檢核(repo 或 service 擋)。
- migration 檔名 `v8_add_api_client_users.py`(接續 v7),upgrade / downgrade 成對;downgrade 只 drop 本 migration 新建之表(新表 round-trip 允許)。
- **禁**動 `users` 表與既有任何表。

## Acceptance

- [x] `cd backend && uv run alembic upgrade head` 成功,`uv run alembic downgrade -1` 後再 `upgrade head` round-trip OK
- [x] `uv run pytest tests/test_api_client_models_repo.py` 全綠(含:建 client + 雙 secret 並存、retire 後 active 只剩一把、`get_by_client_id` 不回軟刪列、client_id 軟刪後可重建同名、status CHECK 違規丟錯)
- [x] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [ ] `uv run pytest` 既有全套仍全綠(由 orchestrator 於波次結束統一跑)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
- `docs/Design-Base/04-databases/08-alembic.md`

## 完成註記(worker-A)

### 驗證命令與結果

| 驗證 | 命令 | 結果 |
| --- | --- | --- |
| migration 單頭 | `uv run alembic heads` | `v8 (head)` 單一頭,無分支 |
| upgrade | `uv run alembic upgrade head` | `v152 -> v8` 成功;`\d` 確認兩表欄位 / CHECK / FK / partial unique index 全符規格 |
| downgrade | `uv run alembic downgrade -1` | `v8 -> v152` 成功;`pg_tables` 查 `api_client%` 0 列,其餘 10 張既有表未動 |
| 再 upgrade | `uv run alembic upgrade head` | `v152 -> v8` 成功,round-trip 完整 |
| 目標測試 | `uv run pytest tests/test_api_client_models_repo.py -q` | **11 passed** |
| lint | `uv run ruff check app tests` | All checks passed |
| type | `uv run mypy app --cache-dir .mypy_cache_t001` | 僅 1 個既存錯誤 `schedule_repo.py:528 Result[Any] has no attribute "rowcount"`(本 task 未動該檔),無新增 |

測試涵蓋:partial unique index / FK 命名 metadata 斷言、create 預設值、雙 active secret 並存 +
第三把擋下(AppError 409)、retire 後 active 剩一把且 retired 列保留、`get_by_client_id`
與 `list_` 不回軟刪列、client_id 軟刪後重建同名、未刪範圍同名撞 IntegrityError、
`update` 只改指定欄、兩表 status CHECK 違規丟 IntegrityError。

### 偏離規格處

1. **`down_revision` 掛 `v152` 而非 `v7`**:task 檔述「接續 v7」係基於過時資訊,實際鏈尾為
   `v152`(`v151_semantic_source_updated_by_uuid.py`)。掛 `v7` 會造成多頭分支,
   `04-databases/08-alembic.md` 明禁「禁孤兒 / 多頭分支」。依〈規範優先順序〉
   Design-Base > Tasks,故掛真正鏈尾;檔名與 `revision` 仍照規格為 `v8`。
2. **`get_by_client_id` 回傳 `tuple[ApiClientUser, list[ApiClientSecret]] | None`**:規格要求
   「僅回傳含 active secrets 所需資料」。專案全域無任何 ORM `relationship` / `selectinload`
   用法(既有 repo 一律顯式 select),故不引入 relationship,改以 tuple 回傳 client +
   active 密鑰清單。附帶公開 `list_active_secrets` 供 `add_secret` 上限檢核與呼叫端複用。
3. **加 `soft_delete`**:Acceptance 要求驗證「client_id 軟刪後可重建同名」,規格 6 個方法
   無刪除入口;依 `02-soft-delete.md` 補 `soft_delete`(命名照 `schedule_repo.soft_delete`)。
4. **`create` 不做應用層 status 驗證**:CHECK 約束為單一事實來源,Acceptance 亦要求
   「status CHECK 違規丟錯」由 DB 擋(IntegrityError),故不另加 `ensure_valid_status`。

### 其他注意

- `backend/.mypy_cache_t001/`(依派工要求的獨立快取目錄)未被 `.gitignore` 涵蓋
  (只有 `.mypy_cache/`),commit 前請勿納入版控。
