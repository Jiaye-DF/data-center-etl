# 04-datetime — 日期時間顯示

> **何時讀**:寫日期時間顯示元件時讀。

對齊 DB 時區策略(`04-databases/06-timezone.md`)。若 DB 存 UTC+8 wall-clock:**禁** `new Date(...).toLocaleString` / 帶 `timeZone`。統一 `utils/datetime.ts` 入口,**禁**各頁自寫。

```ts
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/);
  return m ? `${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}:${m[6]}` : iso;
}
```
