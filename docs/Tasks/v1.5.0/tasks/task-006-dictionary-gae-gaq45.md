---
id: task-006
title: 字典擴充 — GAE 畫面標籤 fallback + GAQ04/05 選項值進 comment(B1+B3)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/etl/dictionary.py
  - backend/tests/test_dictionary.py
estimated_hours: 3
---

## 目標

擴充執行期字典 `dictionary.py`:(B1)GAQ 查不到欄中文名時退 `DS.GAE_FILE` 畫面標籤(可補 126/191 缺漏欄);(B3)GAQ04/05 選項代碼值(如 `1.單檔 2.單檔多欄…`)附加進欄 comment。

## 內容

- **B1 GAE fallback**:`fetch_column_comments` 批量查 GAQ 後,對仍缺者批量查 `DS.GAE_FILE`(`GAE02`=欄名(小寫)/`GAE03`=語別/`GAE04`=標籤;繁 `'0'` 優先缺退簡 `'2'`,同一欄多畫面取第一筆非空標籤);`GAE_FILE` 表不存在時 graceful 略過(沿用 `_dict_table_exists` 模式,**不 raise**)— 對應 DMS 尚未加表的過渡期。
- **B3 GAQ04/05**:GAQ 查詢加取 `GAQ04`/`GAQ05`;有值且**不等於中文名**(去空白比對,排除無資訊量重複)→ comment 組為 `<中文名>；<說明/選項值>`;僅 GAQ03 有值則維持現行輸出(既有 comment 不變動)。
- 查詢模式一字不差對齊現行:識別字白名單常值硬編於 SQL、值走 bind params、繁優先缺退簡迴圈。
- 消費端(`mirror.py`/`snapshot_service.py`)**不改**——擴充只發生在 dictionary 回傳值內。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_dictionary.py` 全綠(新增案例:GAQ 缺→GAE 補、GAE 表缺 graceful 回空、GAQ04 有值附加、GAQ04=中文名不附加、繁缺退簡)
- [ ] `uv run pytest` 既有全套件不紅(mirror/snapshot 相關測試不受影響)
- [ ] ruff + mypy 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`

## 前置(非程式)

- B1 實際生效需 DMS 任務加 `DS.GAE_FILE` 複寫(source 用 sys,無需授權)— **人工操作,不阻塞本 task**(graceful 設計已涵蓋未加表期間)。
