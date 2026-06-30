# 03-env-and-auth — env 前綴 + 認證

> **何時讀**:client config / 登入 / SSO 才讀。

## 環境變數前綴

- Next.js → `NEXT_PUBLIC_*`
- Vite → `VITE_*`

**禁**客戶端引用無前綴 env(編譯為 undefined,且可能洩漏)。Client secret **禁**進前端 bundle。所有 env 須登記於 `.env.example`。

build-time env 改值須重啟 dev server / 重 build(`NEXT_PUBLIC_*` / `VITE_*`)。

## 認證(httpOnly cookie 由後端設定)

- JWT 透過後端 `Response.set_cookie(httponly=True, secure=True, samesite="lax")`
- 前端**禁**讀寫該 cookie
- 取登入狀態一律透過共用 `useAuth`(內部 RTK Query `useGetMeQuery`)
- SSO callback 須驗 state CSRF
