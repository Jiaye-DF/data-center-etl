# 01-fixed-md — fixed.md 規範

> **何時讀**:寫 fixed.md 條目時讀。

`tasks-v*.md` = 實作前規格、commit message = 事件流水;**`fixed.md` 補上「為什麼會發生 / 根因 / 影響範圍 / 同類如何避免」**。

## 寫入時機

修改既有程式碼且符合任一情境**必**寫入 `docs/Tasks/v{X.Y.Z}/fixed.md`(3-digit semver,例 `v1.0.0`):

- bug 修補 / 設定 / env / migration 基礎設施錯誤
- 既有規格實作偏差
- 第三方升級 / API 變動 breaking change
- 效能 / 安全性回填

**不需寫入**:純依 `tasks-v*.md` 新功能、純文件 / 註解、不改行為的重命名 / 重構。

## 條目格式

```markdown
## N. <簡述>  〔YYYY-MM-DD HH:MM:SS〕

**問題**:<現象 / log>

<根因:何時被埋下、為何先前未暴露>

**修正**:<處置;多步驟 1./2./3.>

**影響檔案**:
- `path/to/file`
```

時間 `YYYY-MM-DD HH:MM:SS`(`Asia/Taipei`),全形〔〕標題尾。一條 = 一個問題;**根因**段是核心;沒寫清根因視為品質不合格。

## 雙向引用

fixed.md 涉及 task 規格被推翻 → 條目尾段附 `見 tasks-vX.Y.Z.md §N`;對應 task checkbox 後方補 `—(已改為 xxx,見 fixed.md §N)`。

## 跨版本既存問題

非當版本引入但本版掃描出的舊規範違反 → 仍寫入**當版** `fixed.md`,但**必**:

1. 簡述後加 `(既存自 v{X.Y.Z})`
2. 根因段交代:在哪個版本 / PR 被引入 + 為何先前未暴露
3. 同類重複出現 → 條目末加 `> 同類追蹤:見 vX.Y.Z/fixed.md §N`

`fixed.md` 是**該版本的品質演進真相**;不回填到舊版。
