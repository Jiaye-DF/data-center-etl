# 08-df-sso — DF-SSO 中央登入器整合

> **何時讀**:本專案要接公司 **DF-SSO 中央登入器**才讀。實際落檔走 `sso-init` skill;本檔是 skill 隨附 `INTEGRATION.md` 的**宣告式契約子集**,兩者同源。

**DF-SSO ≠ 直連 Azure AD**。`04-sso-azure-ad.md` 是 App 自己當 OAuth client 直連 `login.microsoftonline.com`(自存 user、自簽 session);本檔是 App 串公司自架的 DF-SSO 中央——**App 不碰 OAuth、不存 user**,`/me` 每次回源中央 Redis。兩條路**擇一**,不可混用。

---

## 4 條硬性契約(永遠遵守)

中央**無法強制驗證**,全靠自律。漏一條就壞:

1. **`/me` 即時回源中央** — 本地驗證端點必以 `Authorization: Bearer <token>` 把每次請求轉發中央 `/api/auth/me`。**JWT 簽名有效 ≠ session 仍存在**;**禁**在本地快取 user、**禁**只驗 JWT 簽名就回。
2. **登出 POST 中央 + 跟隨 redirect** — 收到本地 logout 請求,必先以 Bearer POST 中央 `/api/auth/logout`,再 302 到回應的 `redirect` / `logout_url`。只清本地 cookie → 中央 session 還活著,下次 silent SSO 把人拉回。
3. **登入頁 401 不自動 redirect** — 登入頁 401 顯示「透過 SSO 登入」按鈕,**禁**自動跳 `/authorize`(嚴格模式;Portal 模式例外見下)。**僅限登入頁**;dashboard / protected 頁 401 走 silent re-auth。
4. **Back-channel logout 必驗 HMAC + timestamp** — 演算法 `HMAC-SHA256`,訊息 `"${user_id}:${timestamp}"`,密鑰 `app_secret`;**必用 constant-time 比對函式**(禁 `==` / `equals`),並驗 `abs(now_ms - timestamp) ≤ 30000`。**保留無驗證的空端點 比 不註冊還糟**——不需要主動清理時,整條路由拿掉。

## 5 端點行為契約(永遠遵守)

路徑為慣例建議,命名可調,行為不可變:

| 端點 | 契約 |
| --- | --- |
| `GET /callback` | 驗 `code` → POST 中央 `/api/auth/sso/exchange`(帶 `client_secret`)→ 取 `token` 寫 cookie → 302 dashboard;失敗 302 回登入頁帶 `?error=` |
| `GET /me` | 取 cookie token → 缺則 401 `no_token`;否則 Bearer 打中央 `/me`。中央 200 原樣回(**不加快取**);中央 401 → 回 401 `session_expired` **且刪本地 cookie**;中央不可達 → 502 `sso_unreachable`(**不刪 cookie**) |
| `GET /logout` | Bearer POST 中央 `/api/auth/logout` → 跟隨回應 `redirect` / `logout_url`;取不到則落 fallback(`<app_origin>/?logged_out=1`)。**不論成敗同一 response 刪本地 cookie** |
| `POST /back-channel-logout` | 依契約 #4 驗 HMAC + timestamp;模式 A 通常無事可做(可不註冊),模式 B 只清 `provider="sso"` 的 session |
| `GET /`(登入頁) | 進頁打自家 `/me`:200 → dashboard;401 → 依模式顯示按鈕或 silent re-auth |

Cookie 屬性固定:`HttpOnly` / `Secure`(prod)/ `SameSite=Lax` / `Max-Age=86400` / `Path=/`。所有 server-to-server 呼叫等價 `cache: no-store` + 顯式 timeout ≤8s。

## 兩種整合模式(必擇一)

| 模式 | 適用 | token 驗證 |
| --- | --- | --- |
| **A. 純 SSO** | App 無自有帳號系統 | 只有一條路:每次必打中央 `/me`;本地不存 session、不需 `JWT_SECRET` |
| **B. 本地帳密 + SSO** | App 有自有帳號表 | JWT payload 必帶 `provider`(`"sso"` / `"local"`);守衛分流:`sso` → 打中央,`local` → 查自家 session store |

模式 B 核心契約:**session 一被清,token 立即失效**。`provider` 決定走哪條路——SSO 來源 token **一律即時驗中央**。

## 登入頁模式(契約 #3 細則)

每個 App **必須**在兩者間明確擇一,不可混用:

| 模式 | 登入頁 401 行為 | 適用 |
| --- | --- | --- |
| **嚴格模式(預設)** | 顯示按鈕,**禁**自動 redirect | 對外 / 含敏感操作(金流、客戶資料、審批) |
| **企業 Portal 模式** | 無 cookie / 401 → 自動 `window.location.href = <auth-login-url>` | 全公司內部 admin 工具 |

共同底線:都**不可**在 `?logged_out=1` 等明確登出旗標下自動 redirect(Portal 模式必須保留這個例外);dashboard 工作中 401 兩模式都走 silent re-auth;契約 #1/#2/#4 兩模式都遵守。

模式 B 的 Portal 模式必須 **provider-aware**(用非機密的 `last_login_provider` hint 決定登入頁顯示),不可盲目 auto-redirect 把本地登入入口藏掉。Portal 模式的「Single Logout 加強」與登出視覺持續性為**選用 UX 加強**,細節見 skill 的 `INTEGRATION.md`。

## Silent Re-Auth(解 dashboard 401 體感 Bug)

JWT 與中央 session 是兩個獨立計時器。dashboard / protected 頁面工作中 401 → **禁**直接踢回登入頁。前端 401 攔截器職責:

- **去重**:同頁多個 401 只跑一次 re-auth
- **重試上限**:瀏覽器級 storage 記次數,> 2 次踢登入頁帶 `?error=reauth_failed`
- **保留現場**:存當前 path + query,dashboard 進入點負責復原
- **跳轉**:整頁 navigate 到 `<SSO_URL>/api/auth/sso/authorize?...`

模式 B:先 `/me` 取 `provider` 分流——`sso` → silent re-auth;`local` → 跳本地登入頁。

## env(永遠遵守)

| 變數 | 範圍 | 用途 |
| --- | --- | --- |
| `SSO_URL` | server + 可公開 | 中央 backend URL |
| `SSO_APP_ID` | server + 可公開 | 此 App 的 ID(IT 發放) |
| `SSO_APP_SECRET` | **server only,禁前端** | 換 token + 驗 HMAC(IT 發放) |
| `APP_URL` | server + 可公開 | callback / redirect 用的對外 origin |

`SSO_APP_SECRET` **絕不**出現在前端 bundle / browser-readable storage / git。前後端分離時把 `APP_URL` 拆成 `BACKEND_URL`(cookie + callback host)與 `FRONTEND_URL`(登入頁 / dashboard / logout fallback);`redirect_uris` 註冊的是 callback 的 origin(= backend origin)。

對齊 `00-overview/02-secrets.md`:`SSO_APP_SECRET` 為機密,走 env 注入。

## 不要做

- ❌ 本地快取 user / 只驗 JWT 簽名就回(違契約 #1)
- ❌ 登出只清本地 cookie 不通知中央(違契約 #2)
- ❌ 登入頁 401 自動 redirect 到 `/authorize`(違契約 #3;Portal 模式也要保留 `?logged_out=1` 例外)
- ❌ back-channel 用 `==` / `equals` 比對簽章,或留無驗證的空端點(違契約 #4)
- ❌ 把 `SSO_APP_SECRET` 帶進前端(對齊 `02-frontend/03-env-and-auth.md`)
- ❌ dashboard 工作中 401 直接踢登入頁(要 silent re-auth)
