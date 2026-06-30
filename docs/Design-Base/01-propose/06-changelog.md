# 06-changelog — 對外 CHANGELOG 格式

> **何時讀**:版本 release 前寫對外 CHANGELOG 才讀。

對齊 [Keep a Changelog](https://keepachangelog.com/zh-TW/) 簡化版,**user-facing 語意化**。內部根因細節在 `fixed.md`,**禁**寫進 CHANGELOG。

---

## 格式

```markdown
# CHANGELOG

## [Unreleased]
<開發中未發布的條目>

## [v1.1.0] — 2026-05-07

### 新增(Added)
- 使用者群組(user-groups)管理:列表 / 新增 / 編輯 / 軟刪
- Azure AD SSO 登入

### 變更(Changed)
- `/api/v1/users` 回應加 `groups` 欄位(向下相容)

### 修復(Fixed)
- 使用者列表頁分頁失效(影響 `v1.0.0`–`v1.0.3`)

### 棄用(Deprecated)
- 舊 `/api/v1/login` endpoint;下版移除,改走 SSO

### 移除(Removed)
- (本版無)

### 安全(Security)
- 升級 `passlib` 至 1.7.4(CVE-2025-XXXX 修復)
```

---

## 規則

- 條目用 user 看得懂的語言;**禁**內部變數名 / commit hash / 員工名
- 一條 = 一個 user-facing 行為;不是一個 commit
- **禁**露機密 / 內部架構細節 / 第三方 API key / 內部 endpoint
- breaking 變更明標「⚠️ Breaking」+ 遷移指引連結
- 連結 issue / PR 用 `#NN`(GitHub 自動連結)
- 版本日期用 `YYYY-MM-DD`(時區 +08,但 CHANGELOG 簡化只寫日期)
- 條目順序:Added → Changed → Fixed → Deprecated → Removed → Security(語意化排序)

## 與 `fixed.md` 的差異

| | CHANGELOG.md | fixed.md |
| --- | --- | --- |
| 對象 | user / 客戶 | agent / 內部 reviewer |
| 內容 | 行為變更 | 規範違反 + 根因 |
| 寫法 | 語意化(列功能) | 條目化(根因 + 修正)|
| 何時更新 | release 前彙整 | 每個違規當下 |
| **禁** | 內部細節 / commit hash | 模糊根因(「忘了」) |

## release 前 checklist

- [ ] `[Unreleased]` 段內容搬到新版本 heading 下
- [ ] 新版本日期填妥(+08)
- [ ] breaking 條目標 `⚠️ Breaking` 並附遷移指引
- [ ] 連結 PR / issue
- [ ] 對外承諾欄(`propose-v*.md § 對外承諾`)的條目已反映
