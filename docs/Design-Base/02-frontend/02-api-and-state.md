# 02-api-and-state — API 呼叫集中 + 狀態管理

> **何時讀**:data fetching / 狀態管理任務時讀。

## API 呼叫集中

元件**禁**直呼 `fetch` / `axios`。一律走 `lib/api/*` 或 RTK Query(`createApi` + endpoints)。後端 base URL 由 env 注入,**禁**寫死。

## 狀態管理三層

- **全域**(語系 / 主題 / 登入態):Redux Toolkit slice
- **伺服器資料**(列表 / 詳情):RTK Query;**禁**自管 loading / error / cache
- **元件本地**:`useState` / `useReducer`,**禁**提升至全域
