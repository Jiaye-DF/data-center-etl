# 06-timezone — 時區

> **何時讀**:寫時間欄位才讀。

DB schema `TIMESTAMP` / `TIMESTAMPTZ` 須與顯示層轉換策略**全棧一致**(`00-overview/05-timezone.md`、`02-frontend/04-datetime.md`)。container `TZ=Asia/Taipei` + DB session timezone 對齊。**禁**前後端各做時區轉換 → 雙偏移。
