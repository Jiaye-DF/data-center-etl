# 03-pr-self-check — PR Self-check

> **何時讀**:發 PR 前讀。

PR 前**必過**:

## 共同
- [ ] 規範遵守 `docs/Design-Base/*.md`
- [ ] `tasks-v*.md` checkbox 與頂部狀態一致
- [ ] `fixed.md` 條目(若觸發寫入時機)
- [ ] `.env.example` 同步新引用的 env
- [ ] 機密未入 commit:`git diff --staged | grep -iE "(secret|token|password|key)\s*[:=]"`
- [ ] Frontend:`npm run lint && npm run typecheck && npm run test`
- [ ] Backend:`uv run ruff check . && uv run pytest`
- [ ] CI audit 無新 high/critical
- [ ] commented-out code 已清

## 後端
- [ ] route response 用 Pydantic schema(非 `dict`)
- [ ] 受保護 endpoint 加 `Depends(require_*)`
- [ ] CPU-bound 同步操作已 `asyncio.to_thread`
- [ ] Service 多表寫入已 `async with db.begin():`
- [ ] 新加 secret 已進 `Settings._fail_fast_in_prod`
- [ ] 新 Repository `find_*` 預設過濾 `is_deleted`;不過濾版命名 `_including_deleted`

## 前端
- [ ] 元件未直 `fetch` / `axios`(走 RTK Query / `lib/api/`)
- [ ] 客戶端 env 用 `NEXT_PUBLIC_*` / `VITE_*`
- [ ] TS 無 `any`;props 獨立 `interface`
- [ ] callback `useCallback`、衍生 `useMemo`、列表元件 `React.memo`
- [ ] 文字走 i18n key;所有語系同步
- [ ] UI 不顯示 `*_uid`
- [ ] 字級不小於 `text-base`(密集 `text-sm md:text-base`)
