# 05-version-bump — 版本判準

> **何時讀**:決定 propose 用哪個版號 / API 是否要 bump major 才讀。

採用 **SemVer 3-digit**:`major.minor.patch`(`X.Y.Z`)。檔案 / 資料夾命名統一 `v{X.Y.Z}`(例 `propose-v1.0.0.md` / `tasks-v1.1.0.md` / `docs/Tasks/v1.0.0/`)。

---

## 判準

| 變更性質 | bump | 例 |
| --- | --- | --- |
| **breaking change** — API 路徑 / 回應 schema 不相容 / DB schema 不可逆 | **major**(`v1.0.0 → v2.0.0`) | `/api/v1/users` → `/api/v2/users` 並改回應 schema |
| 新功能 / 新 endpoint / 新表 / 向下相容的欄位新增 | **minor**(`v1.0.0 → v1.1.0`) | 加 `/api/v1/user-groups`;`/users` response 加 `groups` 欄位 |
| bug fix / 非 user-facing 重構 / lint 修正 | **patch**(`v1.0.0 → v1.0.1`) | 修 N+1 / 改命名 / 補測試 |
| **規範升級**(`docs/Design-Base/*`) | 走 Harness-Engineering git tag(`harness-engineering-vX.Y`),**不** bump 應用版號 | — |

## propose 與版號

- `propose-v1.0.0.md` / `propose-v1.1.0.md` / `propose-v2.0.0.md`(對應 minor / major,patch 槽位 `0`)
- patch **不**寫 propose,直接 commit + `fixed.md`;patch 的 fixed 寫進**該 minor 的 anchor 資料夾**(例:`v1.0.1` 的 fix → `docs/Tasks/v1.0.0/fixed.md`)
- 同一 minor 內 patch 累積 ≥ 5 → 考慮升 minor 包裝對外

## breaking change 判定

下列任一視為 breaking,**必** bump major:

- API endpoint 移除 / 路徑改名
- API response schema 欄位移除 / 改名 / 改型別
- API request 必填欄位新增(舊 client 沒帶會失敗)
- DB column 移除 / 改型別(資料層 breaking,即使 API 沒動)
- 認證 / 授權邏輯改動(權限收緊,既有 user 失去存取)

下列**不**是 breaking(走 minor):

- API response 加新欄位(舊 client 忽略)
- API request optional 欄位新增
- DB 加 column / 加 index
- 內部重構(同 endpoint 行為不變)

---

## 對外宣告

minor / major bump → 同步:
- `CHANGELOG.md`(`06-changelog.md`),版本標 `[v1.1.0]`
- API `/api/v{X}` 或 `/api/v{X.Y}` 路徑(major 必開、minor 視情況開;**禁** patch;細節見 `03-backend/01-routing.md § 版本化`)
- 第三方文件 / SDK 通知(僅 major,需附遷移指引)
- 部署 PR description 標 `⚠️ Breaking`

## 版本停用

- API major 退場前留 ≥ 1 個 minor 的棄用期(CHANGELOG `Deprecated` 段標記)
- DB column 退場走兩階段:標 `is_deleted` / 雙寫 → 下版移除(對應 `04-databases/02-soft-delete.md`)
