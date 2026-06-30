# 05-timezone — 時區

> **何時讀**:任何時間相關任務讀。本檔定義**全棧時區底線**;DB schema 細節見 `04-databases/06-timezone.md`,前端顯示見 `02-frontend/04-datetime.md`。

---

## 全棧鎖 UTC+8 / Asia/Taipei

後端 / PostgreSQL / log / container 一律 **UTC+8 / Asia/Taipei**。專案可調,但**全棧一致**;禁某一層用 UTC、另一層用 +08。

## 後端 datetime 實踐

- 取現在時間:`datetime.now(ZoneInfo("Asia/Taipei"))`(aware)
- **禁** `datetime.utcnow()` / `datetime.now()`(naive 無 tz);Python 3.12+ `utcnow()` 已 deprecated
- 統一寫 `app/utils/datetime.py` 並 export `now_tw()` / `to_tw(dt)`;各層 import 同一處,**禁**各 service 自寫

## Container 時區

Dockerfile / compose **必**設 `TZ=Asia/Taipei`(對齊 `06-Coolify-CD/02-dockerfile-backend.md` / `01-compose.md`);**禁**遺漏導致 container `date` 為 UTC、log 時戳偏移。

```Dockerfile
ENV TZ=Asia/Taipei
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
```

## Log 時戳格式

ISO 8601 + offset:`2026-05-07T14:23:00+08:00`(**禁**裸 `2026-05-07 14:23:00` 無 tz);結構化 log 規範見 `03-backend/05-exceptions-and-logging.md`。

## 資料庫

`TIMESTAMP` / `TIMESTAMPTZ` 與顯示層轉換策略對齊;細節見 `04-databases/06-timezone.md`。container `TZ=Asia/Taipei` + DB session timezone(`SET TIME ZONE 'Asia/Taipei'` 或 connection string `?options=-c%20TimeZone%3DAsia/Taipei`)對齊。

## 前端

**禁**自做時區轉換(避免雙偏移);細節見 `02-frontend/04-datetime.md`。

## Bash 取系統時間

- ✅ `date "+%Y-%m-%d %H:%M:%S"`(container `TZ=Asia/Taipei`,輸出已是 +08)
- ❌ `TZ=Asia/Taipei date`(若 container 已是 +08 → 雙轉換)
- ❌ Windows PowerShell `Get-Date` 直接輸出(取決於 OS 設定,不可預期)→ 用 `[DateTime]::Now.ToString("yyyy-MM-dd HH:mm:ss")` 或於 container 內 `docker exec`

## 跨時區資料源

若必須接外部 UTC API(例 Stripe webhook):於 client 邊界**立即**轉 `Asia/Taipei`(於 `app/clients/<service>/`),內部所有層保持 +08;**禁**讓 UTC datetime 流入 service / repository。
