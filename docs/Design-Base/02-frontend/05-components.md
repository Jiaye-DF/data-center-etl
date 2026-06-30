# 05-components — 共用 Hook / Component / Utility

> **何時讀**:寫任何 component / hook / 工具函式都讀(本檔規範**所有可重用單元**的拆檔規則)。

---

## Reuse 規則(永遠遵守)

**任何被 ≥ 2 個地方使用的單元 → 必抽出共用檔**,**禁**在頁面內 inline 重複定義。

| 單元類型 | 抽出位置 | 條件 |
| --- | --- | --- |
| **Component**(TSX) | `components/common/<Name>.tsx` | 跨頁 ≥ 2 次使用,或預期會被重用 |
| **Hook**(`use*`) | `hooks/<useName>.ts` | 跨檔 ≥ 2 次使用,或封裝具獨立語意的副作用 / 狀態 |
| **純函式 / utility** | `utils/<name>.ts` | 跨檔 ≥ 2 次使用,或為跨領域邏輯(日期 / 格式化 / 計算) |
| **Type / Interface** | `types/<name>.ts` 或 `<feature>/types.ts` | 跨檔 ≥ 2 次使用 |
| **常數** | `constants/<name>.ts` 或 `<feature>/constants.ts` | 跨檔 ≥ 2 次使用 |

> ✅ ≥ 2 = 抽出來;**禁**用「現在還沒重用」當理由 inline。複製貼上第二次的當下就抽。
>
> ❌ 例外:純樣式組合(`className="..."`)若只是 Tailwind class 串,**不**值得抽元件;但若有條件邏輯(`active` / `disabled` 變樣式)→ 抽元件。

## 拆解原則

- **單一職責**:一個 component / hook / utility 做**一件事**;名字描述該事(`<UserAvatar>` / `useDebounced` / `formatCurrency`)
- **不依賴頁面 context**:共用元件**禁** import 特定 page 的 props / store slice;改透過 props 傳入
- **不假設樣式環境**:容器寬度由父決定(對齊 `06-rwd.md § Container Queries`)
- **明確 interface**:Props 一律獨立 `interface`(對齊 `00-overview.md § TypeScript 嚴格`),**禁**匿名行內 type
- **無副作用**:utility 為 pure function;有狀態 / IO → 改寫成 hook

## 必抽 component / hook 清單

下列場景**必**走共用,**禁**頁面自寫:

| 場景 | 共用 |
| --- | --- |
| Dialog / Modal(含 overlay / ESC / portal / focus trap) | `<Dialog>` / `<ModalDialog>` |
| 確認對話框 | `useConfirmMutation` / `<ConfirmDialog>` |
| 原生 `alert` / `confirm` / `prompt` | **禁**使用,改 `useDialog` |
| 列表 cursor 分頁 | `useCursorPagination` |
| 列表過濾 / 搜尋 | `useFilteredList` |
| Mutation + dialog | `useMutationWithDialog` |
| Breakpoint 偵測 | `useBreakpoint`(對齊 `06-rwd.md`) |
| 日期格式化 | `formatDateTime`(對齊 `04-datetime.md`) |
| API 呼叫 | RTK Query endpoint(對齊 `02-api-and-state.md`) |
| Toast / 通知 | `useToast` / `<Toaster>` |
| 表單驗證 | `<Form>` + 統一 schema(視專案選 zod / valibot) |

## 抽出時機

- **複製貼上的當下**(寫第二次時就抽,**禁**等到第三次)
- **PR review 抓到重複** → 抽出來再 merge,**禁**「下個 PR 補」(會無限延期)
- **已存在共用但被繞過** → 改回走共用 + 寫 `fixed.md`(根因:沒有讀 `05-components.md`)

## 命名與位置

```
frontend/src/
├── components/
│   ├── common/          # 跨 feature 共用 component
│   │   ├── Dialog.tsx
│   │   ├── Button.tsx
│   │   └── ...
│   └── <feature>/       # 該 feature 專用 component
│       ├── UserCard.tsx
│       └── ...
├── hooks/
│   ├── useBreakpoint.ts
│   ├── useDebounced.ts
│   ├── useConfirmMutation.ts
│   └── ...
├── utils/
│   ├── datetime.ts
│   ├── formatCurrency.ts
│   └── ...
├── types/
│   └── api.ts
└── constants/
    └── breakpoints.ts
```

對齊 `00-overview.md § 命名`(PascalCase / `use` 前綴 / camelCase)。

## 禁忌

- ❌ 在 page 檔內定義超過 1 個共用候選元件(超過 → 立即抽 `components/`)
- ❌ 元件超過 ~200 行還沒拆(可能是多個職責混雜)
- ❌ Hook 內混多個無關副作用(切成多個 hook)
- ❌ utility 內 import React(那不是 utility,是 hook)
- ❌ 共用元件 import 特定 page / feature 模組(走 props 傳入)
- ❌ inline 重複的條件樣式邏輯(抽成 component / `cva` variant)

## 跨領域對應

- API 呼叫共用 → `02-api-and-state.md`(RTK Query 集中)
- 日期共用 → `04-datetime.md`(`utils/datetime.ts`)
- 響應式共用 → `06-rwd.md`(`useBreakpoint`)
- 路由錯誤共用 → `01-routing-and-error.md`(`<ErrorBoundary>` / `global-error.tsx`)
