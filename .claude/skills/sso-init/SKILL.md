---
name: sso-init
description: 在當前專案自動建立 DF-SSO 登入器整合（callback / me / logout / back-channel-logout 四端點 + 登入頁 + auth middleware / 受保護路由守衛）。支援 FastAPI / Next.js / Spring Boot 三種後端框架,執行時先詢問框架再分流到對應變體檔。當使用者說「接 DF-SSO / 串公司 SSO / 整合 SSO 登入 / sso-init / 接 AD 登入閘道」時觸發。契約見隨附 INTEGRATION.md。
---

# sso-init

把「當前專案」接上公司 **DF-SSO 中央登入器**的單入口 skill。本 skill 只負責**分流**——詢問後端框架 → 載入對應變體檔 → 依該檔逐步落檔;真正的端點設計、程式碼骨架與停等規則寫在三個變體檔裡。

> **DF-SSO ≠ 直連 Azure AD**。本 skill 接的是公司自架的 DF-SSO 中央(App 不碰 OAuth / 不存 user,`/me` 即時回源中央 Redis)。若要 App 自己當 OAuth client 直連 `login.microsoftonline.com`,那是另一條路,見 `docs/Design-Base/90-third-party-service/04-sso-azure-ad.md`。

## 隨附檔案

| 檔 | 用途 |
| --- | --- |
| `INTEGRATION.md` | **契約正本**——5 端點行為、4 條硬性契約、模式 A/B、嚴格 vs Portal 模式、silent re-auth。不綁語言。**查契約一律讀這份**,不要連到專案外的相對路徑 |
| `sso-init-fastapi.md` | 變體:Python FastAPI(`httpx.AsyncClient` + `pydantic-settings` + `Depends(require_auth)`) |
| `sso-init-express.md` | 變體:Next.js 15 App Router(Node runtime,`withAuth` / `requireAuth` HOF) |
| `sso-init-spring.md` | 變體:Java Spring Boot 3.x(Controller + Service + `OncePerRequestFilter`) |

> 對應的 Design-Base 宣告式契約見 `docs/Design-Base/90-third-party-service/08-df-sso.md`(套用 Harness-Engineering 的專案才有)。本 skill 與該檔同源——契約被改一處,另一處同步。

## Agent 能力基線（跨 AI Model）

本 skill 是**模型無關**的執行指南,適用任何具備「讀檔 / 寫檔 / 執行 shell」能力的 AI agent(Claude Code / Codex / Cursor / Cline 等)。

- **Claude Code / 具備 AskUserQuestion 的 agent**:框架選擇與變體檔內「詢問使用者」各項,優先用互動式提問元件收集;沒拿到答案前不得落檔。
- **Codex / 無互動式提問元件的 agent**:以純文字一次列出問題並停下等待回覆;收到回覆後再繼續。
- **其他 agent**:若只能對話,也必須遵守同樣停等規則;工具更強只可**加強**遵守程度,不可降低。
- 變體檔的「詢問使用者」與「需要使用者處理」兩節是**硬性停等點**:在使用者明確回覆前,**禁止**自行編造值、用 placeholder 帶過、或跳過往下執行。

## 執行步驟

### 1. 詢問後端框架(硬性停等)

問使用者當前專案的後端框架,**收到回覆才往下**:

| 選項 | 載入變體檔 |
| --- | --- |
| **Python FastAPI** | `sso-init-fastapi.md` |
| **Next.js(App Router)** | `sso-init-express.md` |
| **Java Spring Boot** | `sso-init-spring.md` |
| 都不是 | **停下**,告知使用者本 skill 目前只支援上列三種框架,請改用 INTEGRATION.md 的「跨框架落地對應」表自行對應(Go / Express Pages Router 等) |

> 若使用者已在觸發語句裡點名框架(例如「用 sso-init 接這個 FastAPI 專案」),可略過詢問直接分流;框架不明時**必問**。

### 2. 載入契約 + 變體檔

1. 讀 `./INTEGRATION.md` 建立契約認知(硬性契約 #1–#4、5 端點、模式 A/B)。
2. 讀 § 1 選定的變體檔。

### 3. 依變體檔逐步執行

完整照變體檔的「詢問使用者 → 前置檢查 → 執行步驟 → 顯示完成訊息」走。本 SKILL.md **不重述**變體檔內容,也**不**改寫變體檔的步驟——變體檔即真實規格。

## 硬性規則(任何框架共通)

- 變體檔的停等點(詢問使用者 / 需要使用者處理)**不可**跳過或自填。
- `SSO_APP_SECRET` **絕不**進 git、**絕不**透過任何前端 bundle 暴露。
- `app_id` / `app_secret` 由 IT 發放,agent 無法自取;使用者尚未取得時允許**留空**先落檔,完成訊息**必須**提醒回填。
- 既有檔案(`{sso 目錄}`、`main.py` / `.env` / `.env.local` 等)有衝突時**必問**「整合既有內容」或「允許覆寫」,預設不覆寫。
- back-channel logout 端點要嘛**正確驗 HMAC + timestamp**,要嘛**整條路由不註冊**——**禁**留無驗證的空 handler(契約 #4)。

## 自我約束

- **禁止**自由發揮端點設計——一律照變體檔 + INTEGRATION.md。
- **禁止**在使用者拒絕 / 未回覆停等問題時繼續落檔。
- **禁止**把 `.env` / `.env.local` 等含機密的檔案加進 git 追蹤。
- 落檔後簡述「建立了哪些檔 / 使用者還要做什麼」,引用變體檔的完成訊息即可。
