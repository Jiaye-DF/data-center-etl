# 07-testing — 後端測試

> **何時讀**:寫測試才讀。

- DB 整合測試**禁** mock SQL,須真實測試 DB
- 第三方:`respx` / `httpx.MockTransport`
- 測試檔案結構**對映** `app/`

---

## 測試 DB 生命週期

- 各測試檔自建 `<db>_test`(如 `data_center_etl_test`):連管理庫檢查,**不存在才 CREATE DATABASE**,已存在則沿用
- **禁 DROP**(對齊 CLAUDE.md 毀滅性操作禁止);清理靠交易 rollback / TRUNCATE / 測試自建資料自刪

## Schema 建立

- 測試 schema 以 `Base.metadata.create_all` 建立為**認可做法**;前提:model 與 migration 同源(migration 由 model autogenerate,不得手寫分歧)
- 新增 migration 時,至少一條測試或 CI 步驟以 `alembic upgrade head` 對測試 DB 驗證 migration 可執行(`create_all` 蓋不到 migration 腳本本身的錯)

## Env 注入前置

- Settings 為必填 fail-fast 設計 → **import app 模組前**先設 env(`os.environ.setdefault(...)` 置於測試檔頂部、任何 `app.*` import 之前)— 既有模式,新測試檔沿用
- 任一測試檔**單獨執行**須能通過 collection,不得依賴其他測試檔先注入 env

## 外部服務

- 第三方 HTTP:`respx` / `httpx.MockTransport`,**禁**實連外部服務
- 佇列(taskiq):測試用 `InMemoryBroker` + `await_inplace`;broker 連線行為(timeout / reconnect)InMemory 蓋不到,涉及時須另以實連 redis 煙霧驗證
