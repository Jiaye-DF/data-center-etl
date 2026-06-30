# 02-frontend — 前端入口 + 風格地板

鎖定 **React 19 + TS**(Vite **或** Next.js)+ Redux Toolkit + RTK Query + Tailwind v4。

> **永遠讀**:本檔內容為任何前端任務都必遵守的「風格地板」(TS / 渲染效能 / i18n / ID 隱藏 / 字級下限 / 命名)。子任務專屬規則見對應子檔。

---

## TypeScript 嚴格(永遠遵守)

- `tsconfig.json` 必含 `"strict": true`
- **禁** `any`(改 `unknown` + 型別守衛)
- 函式**必**標參數+回傳型別
- Props **必**用獨立 `interface`(非匿名行內)

```ts
interface AccountCardProps { name: string; onSelect: (uid: string) => void; }
function AccountCard({ name, onSelect }: AccountCardProps): React.ReactNode { ... }
```

## 渲染效能(永遠遵守)

- callback **必** `useCallback`
- 衍生計算 **必** `useMemo`
- 清單元件 **必** `React.memo`
- **禁**在 render 內建立物件 / 陣列字面值作 props

## i18n(永遠遵守)

UI 文字一律 i18n key;字典依模組分檔,新增字串時所有語系同步;缺漏視為 bug。例外:`global-error` 允許硬編碼最低限文字。

## 識別碼隱藏(永遠遵守)

UI **禁**暴露內部 ID(`*_uid` / `pid` / UUID / hash)→ 顯示 name / label,空值用 fallback。例外:URL 路徑、React `key`、form hidden、`error.digest`。

## 字級下限(永遠遵守)

- 桌機(`md+`)body / 表格 / 表單 / nav / 分頁:**最低** `text-base`(16px)
- mobile 密集元素:`text-sm md:text-base`(mobile 14 / 桌機 16)
- **禁**正文用 `text-xs`;例外:group label uppercase / monospace code / hint

## 命名(永遠遵守)

| 對象 | 慣例 |
| --- | --- |
| 元件 | PascalCase(`AccountCard.tsx`) |
| Hook | `use` 前綴(`useAccountList.ts`) |
| 工具函式 | camelCase(`formatDate.ts`) |
| 型別 / 介面 | PascalCase |
| CSS Variable | kebab-case(`--color-background`) |
| 路由目錄 | kebab-case(`app/user-groups/`) |

---

## 子章節(依子任務載入)

- `01-routing-and-error.md` — 路由錯誤邊界
- `02-api-and-state.md` — API 呼叫集中 + 狀態管理三層
- `03-env-and-auth.md` — env 前綴 + httpOnly cookie 認證
- `04-datetime.md` — 日期時間顯示
- `05-components.md` — 共用 Hook / Component / Utility(任何 reuse 必抽)
- `06-rwd.md` — 響應式設計(Mobile-first + Tailwind v4 breakpoints + 觸控目標)
