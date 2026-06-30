# 05-performance-checklist — 效能抽查清單

> **何時讀**:PR review 抽查效能 / 效能優化任務才讀。

reviewer 抽查清單;對應硬規則見 `02-frontend/00-overview.md § 渲染效能`、`03-backend/08-performance.md`、`04-databases/09-indexes-and-perf.md`。

---

## 後端(Python / FastAPI)

- [ ] **N+1**:loop 內查 DB → 改用 `selectinload` / `joinedload` 或預先批次查詢(`04-databases/09-indexes-and-perf.md`)
- [ ] **async 阻塞**:CPU 重 / IO 同步 → 走 `asyncio.to_thread`(`03-backend/03-async-and-tx.md`)
- [ ] **無索引欄查 / 排序**:`WHERE` / `ORDER BY` / `JOIN ON` 對齊索引(`04-databases/09-indexes-and-perf.md`)
- [ ] **大 JSON parse**:第三方回 MB 級 JSON → 用 streaming(`httpx` `iter_bytes`)+ 分段處理
- [ ] **連線池耗盡**:`engine.pool_size` 配置與 worker 數相符(`04-databases/07-connection.md`)
- [ ] **第三方無 timeout**:`httpx.AsyncClient` 必設 timeout(`90-third-party-service/01-client-design.md`)
- [ ] **記憶體洩漏**:大物件 / cursor 未關;long-lived task 未清(對齊 `03-backend/08-performance.md`)
- [ ] **不必要全表掃**:`COUNT(*)` 大表 → 用 estimate(`pg_class.reltuples`)或 cursor pagination

## 前端(React)

- [ ] **render 內字面值**:`<X data={{a: 1}} />` → 抽到 `useMemo` / 模組層常數(`02-frontend/00-overview.md`)
- [ ] **callback 未 useCallback**:傳給 memoized child 的 prop → `useCallback`
- [ ] **衍生計算未 useMemo**:`filtered = items.filter(...)` 每 render 跑
- [ ] **清單元件未 memo**:列表 row 元件用 `React.memo` + 穩定 `key`
- [ ] **大列表未虛擬化**:> 200 列 → `react-window` / `@tanstack/virtual`(視專案加進 `01-versions.md`)
- [ ] **重複 fetch**:無 RTK Query cache → 改走 RTK Query(`02-frontend/02-api-and-state.md`)
- [ ] **bundle 過大**:單頁 chunk > 500 KB → 走 `React.lazy` 切頁面 chunk
- [ ] **錯用 effect**:純衍生狀態用 `useState` + `useEffect` 同步 → 改 `useMemo` / 直接算

## DB

- [ ] **EXPLAIN ANALYZE**:可疑慢 query 跑 plan,Seq Scan 對大表 → 補 index
- [ ] **DISTINCT / GROUP BY**:重 query → 確認真的需要;加索引或重寫
- [ ] **`OFFSET` 大 page**:OFFSET 1000+ → 改 cursor pagination(對齊 `02-frontend/05-components.md` `useCursorPagination`)
- [ ] **缺 partial index**:大表 + 小命中(例 `is_deleted=false`)→ partial index(`04-databases/09-indexes-and-perf.md`)
- [ ] **JSON 欄位無 GIN**:常查 JSON path → GIN index

## 部署

- [ ] healthcheck 內查業務邏輯 / 第三方 → 改僅 `SELECT 1`(`06-Coolify-CD/07-observability.md`)
- [ ] worker 數設過低 / 過高(對齊機器 CPU + memory)
- [ ] DB connection pool 大小 < worker × 應用並行(會連接耗盡)

## 衡量

- 用 `EXPLAIN ANALYZE` / Sentry Performance / Browser Profiler 量,**禁**「感覺慢」
- 把基準寫進 PR description(改前 vs 改後 ms / req/s / RAM)
- 顯著退步(> 20%)→ block PR + 寫 `fixed.md`

## 工具(可選)

- 後端:`py-spy`(profile)、Sentry Performance、`asyncio-debug`
- 前端:Chrome DevTools Performance、React DevTools Profiler、Lighthouse
- DB:`pg_stat_statements` + `pg_stat_user_indexes`
