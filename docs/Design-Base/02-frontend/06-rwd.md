# 06-rwd — 響應式設計(Responsive Web Design)

> **何時讀**:寫任何 UI / 樣式 / 版面任務都讀。本檔規範跨裝置一致體驗;字級下限見 `00-overview.md`。

採 **Mobile-first** + **Tailwind v4 breakpoints**;CSS-only 為主,JS-only RWD 為例外。

---

## Mobile-first(永遠遵守)

預設樣式對應 mobile;`md:` / `lg:` 後綴**只往大螢幕加**,**禁**反向(`md:hidden` 隱藏桌機是錯方向):

```tsx
// ✅ mobile-first
<div className="flex flex-col gap-2 md:flex-row md:gap-4">

// ❌ desktop-first
<div className="flex flex-row gap-4 md:flex-col md:gap-2">
```

## Breakpoints(對齊 Tailwind v4)

| 標籤 | 寬度 ≥ | 對應裝置 |
| --- | --- | --- |
| (預設) | 0 | mobile(直立 / 小螢幕) |
| `sm:` | 640px | 大型手機 / 平板直立 |
| `md:` | 768px | 平板 / 小桌機分界 |
| `lg:` | 1024px | 桌機 |
| `xl:` | 1280px | 寬桌機 |
| `2xl:` | 1536px | 大寬螢幕 |

- **主要切換點**:`md:`(平板 / 桌機分界,> 768px 視為桌機)
- **禁**自定義 breakpoint(除非有明確需求 + 寫進 ADR)
- **禁**用固定 px 改變 layout;一律用 Tailwind 標籤

## Layout primitives

- 用 **Flexbox / Grid**;**禁** float / table-based layout(除真實 table)
- container 統一 `mx-auto max-w-7xl px-4 md:px-6 lg:px-8`(可調但不可省 `mx-auto`)
- **禁**寫死寬度(`w-[1200px]`);用 `max-w-*` + `w-full`
- **禁** absolute / fixed 定位用於主版型(僅限 overlay / dropdown / sticky header)

## 觸控目標(WCAG 2.5.5)

mobile 互動元件**必** ≥ **44×44px**(touch target):

```tsx
// ✅
<button className="min-h-[44px] min-w-[44px] px-4 py-2">確認</button>

// ❌(密集小按鈕,手指點不準)
<button className="text-xs p-1">x</button>
```

- icon-only 按鈕 mobile **必** padding 撐到 44×44
- 連續多個小按鈕 mobile **必**有 ≥ 8px 間距(`gap-2`)
- 桌機可放寬至 32×32(滑鼠精度高)

## 字級(對齊 `00-overview.md § 字級下限`)

- 桌機(`md+`)body / 表格 / 表單 / nav / 分頁:**最低** `text-base`(16px)
- mobile 密集元素:`text-sm md:text-base`(14 / 16)
- **禁**正文用 `text-xs`(12px;閱讀疲勞)
- 標題對應 layout:`text-xl md:text-2xl` / `text-2xl md:text-3xl` 階梯

## 圖片 / 媒體

```tsx
// ✅ 必標 width / height(避免 CLS)
<img
  src="/cover.jpg"
  alt="封面"
  width={1200}
  height={630}
  loading="lazy"
  className="w-full h-auto"
/>

// ✅ 響應式來源
<img
  srcSet="/cover-640.jpg 640w, /cover-1280.jpg 1280w, /cover-1920.jpg 1920w"
  sizes="(max-width: 768px) 100vw, 50vw"
  ...
/>
```

- `<img>` **必**標 `width` / `height`(避免 layout shift,Lighthouse / Core Web Vitals)
- 大圖 `loading="lazy"`;首屏 hero 用 `loading="eager"` + `fetchpriority="high"`
- iframe / video 容器用 `aspect-ratio`(`aspect-video` = 16:9)鎖定
- Next.js 用 `next/image`(自動 srcset + lazy);Vite 自寫上述

## 顯示控制

```tsx
// ✅ CSS-only:mobile 隱藏、桌機顯示
<aside className="hidden md:block">side menu</aside>

// ✅ mobile 顯示、桌機隱藏(漢堡選單)
<button className="md:hidden">menu</button>
```

- **禁** JS 條件 render 大量內容做 RWD(浪費 + 增加複雜度);CSS-only 為主
- 例外:虛擬化大列表 / 動態 dataset(此時用 `useBreakpoint` 等 hook,見下)
- **禁** `display: none` 仍 mount + render 大子樹(用 `hidden` Tailwind class 取代,但內容仍 render — 真要省 cost 改條件 render)

## Container Queries(Tailwind v4)

元件層級 RWD,適合在父容器寬度變化的卡片:

```tsx
<div className="@container">
  <div className="flex flex-col @md:flex-row">
    <Image />
    <Content />
  </div>
</div>
```

- 卡片元件不應該假設視窗寬度,而應假設**父容器寬度**
- 通用元件(`Card` / `Tile`)優先用 `@md:` 等 container queries
- 主版型(`AppShell` / `Header`)用視窗 breakpoints(`md:`)

## JS 偵測(例外)

需要在 JS 拿 breakpoint(虛擬化列表 / 動態 import / dataset 切換)→ 用統一 hook,**禁**各頁自寫 `window.matchMedia`:

```ts
// frontend/src/hooks/useBreakpoint.ts
import { useEffect, useState } from "react";

const BREAKPOINTS = { sm: 640, md: 768, lg: 1024, xl: 1280, "2xl": 1536 } as const;

export function useBreakpoint(bp: keyof typeof BREAKPOINTS): boolean {
  const [match, setMatch] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${BREAKPOINTS[bp]}px)`);
    setMatch(mq.matches);
    const handler = (e: MediaQueryListEvent): void => setMatch(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [bp]);
  return match;
}
```

- 對齊 `05-components.md` 的共用 hook 規範
- SSR 安全(Next.js):`useEffect` 內讀 `window`,首次 render 預設 `false`(server)→ 客戶端 hydrate 後再更新

## 禁忌

- ❌ 用 `useState` + `window.innerWidth` 直接同步(漏 SSR / 漏 resize event)
- ❌ desktop-first 樣式(`md:flex-col` 把桌機改成行)— 違反 mobile-first
- ❌ JS 計算 layout(`getBoundingClientRect`)做主版型;**僅**動畫 / 拖曳允許
- ❌ 寫死像素 breakpoint(`@media (min-width: 800px)` raw CSS)— 用 Tailwind 標籤
- ❌ overflow:hidden 解全部問題;先檢查 flex / grid 設定

## 跨領域對應

- 字級下限 → `02-frontend/00-overview.md § 字級下限`
- 共用 hook(`useBreakpoint` 等)放置 → `02-frontend/05-components.md`
- 圖片 lazy load → 對齊 `99-code-review/05-performance-checklist.md`
