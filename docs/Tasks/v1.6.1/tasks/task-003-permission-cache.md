---
id: task-003
title: Redis 讀取快取層(cache-aside + 異動失效 + 降級直讀)
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/services/permission_cache.py
  - backend/tests/test_permission_cache.py
estimated_hours: 2.5
model: opus
effort: high
---

## 目標

建立權限設定的 Redis 讀取快取層:讀取 cache-aside(miss 回源 RDS 並回填 + TTL 兜底)、寫入後即刻失效、Redis 故障降級直讀 RDS(降級不失能)。此層為模組③「TTL 快取、異動即失效」的地基。

## 實作要點

- key 前綴 `client_setting:`(如 `client_setting:effective:<client_uid>`、`client_setting:list:<resource>`);TTL 預設 300s(常數集中,後續可 env 化)。
- 提供通用 `get_or_load(key, loader)` 與 `invalidate(*keys)` / `invalidate_prefix(prefix)`;序列化 JSON。
- 失效粒度:改設定檔 → 失效綁定該檔 Role 的全部 client effective + 相關 list key;改作業範圍 / 特例 / 指派同理(由呼叫端 service 決定 key 集,本層提供機制)。
- Redis 連線錯誤(連線失敗 / timeout)一律吞下並 fallback 執行 loader(log warning,不拋錯);比照既有 rate_limit fail-open 精神。
- 禁止把明文機密進快取(本層只放權限結構)。

## Acceptance

- [ ] `uv run pytest tests/test_permission_cache.py` 全綠(命中不呼叫 loader、miss 回填後第二次命中、invalidate 後重新 load、模擬 Redis 故障時 loader 照常執行且不拋錯、TTL 有設定)
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/08-performance.md`
