# 01-routing-and-error — 路由錯誤邊界

> **何時讀**:寫 app 結構 / 頁面元件 / 全域錯誤處理時讀。

**必備**:Next.js `app/error.tsx` + `app/global-error.tsx`;Vite 用 React Router `errorElement` 或 `<ErrorBoundary>`。

- 錯誤邊界**禁**顯示業務 uid;允許顯示 `error.digest`
- `global-error` 因樣式未載入,允許 inline style + 中性色 hex

## Suspense 邊界

- 路由級 loading 用 Next.js `app/loading.tsx`(框架已內建 Suspense)
- 用到 `useSearchParams()` / `usePathname()` 等 client hook 的元件**必**包 `<Suspense fallback={...}>`,否則 production build 會 fail(`Missing Suspense boundary`),整頁 bail out 成純 CSR
