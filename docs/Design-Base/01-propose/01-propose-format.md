# 01-propose-format — propose-v*.md 格式

> **何時讀**:啟動新版本 / 寫 propose 才讀。

User 寫 `docs/Tasks/v{X.Y.Z}/propose-v{X.Y.Z}.md`(3-digit semver,例 `v1.0.0` / `v1.1.0` / `v2.0.0`),**Agent 不動本檔**(動了視為違反)。Agent 只**讀**並依此拆 tasks。

---

## 必有區塊

```markdown
# Propose v{X.Y.Z}

## 版本目標
<1–3 句話。本版本要做什麼。寫「為什麼」+「對誰有價值」,**禁**寫實作細節>

## In Scope
- <條目 1>
- <條目 2>

## Out of Scope
- <明確排除的功能 / 重構 / 服務>

## 對外承諾
- <user-facing 行為 / API 契約 / 效能指標 / 上線時間>

## 風險與相依
- 技術風險:<...>
- 第三方依賴:<...>
- 跨團隊阻塞:<...>

## 驗收標準
- <可驗證的成功條件;CI green / e2e pass / 手測 case 清單>
```

---

## 規則

- 版本檔名 `X.Y.Z`:**major.minor.patch**(3-digit semver);patch 不獨立 propose(patch 直接 commit + `fixed.md`,細節見 `05-version-bump.md`)
- propose 對應 minor / major bump,patch 槽位寫 `0`(例 `propose-v1.0.0.md` / `propose-v1.1.0.md` / `propose-v2.0.0.md`)
- **In Scope** 條目須能對應到 ≥ 1 個 task(由 orchestrator 驗證)
- **對外承諾** 明寫 API path / 行為,作為 Acceptance 來源
- **禁**寫實作細節(屬於 tasks 職責);只寫「**做什麼**」+「**不做什麼**」
- 未列入 Scope 的需求 → orchestrator **拒絕**拆 task,user 須先更新 propose

## propose 變更

- 拆 tasks 之前可自由改
- 拆完後改須:
  - 註記 `## 變更紀錄` 區塊(日期 / 改動 / 理由)
  - orchestrator 重跑拆解,列受影響 tasks
- propose 鎖定後(multi-agent 已開跑)→ 改動視為 scope creep,bump 至下版
