"""taskiq + redis 排程執行層(v1.1.0):broker / worker task / scheduler。

- `broker.py`:redis broker(URL 由 env `REDIS_URL` 注入,缺值 fail-fast);
  pytest 環境自動退 InMemoryBroker(不連 redis)。
- `tasks.py`:worker task `run_etl` — 呼叫 `app.etl` engine,
  確保 run 狀態落 DB(引擎外例外也補標 failed,不留 running 殭屍)。
- `scheduler.py`:taskiq scheduler,以自有 DB `schedules` 表為排程來源,
  cron 一律以 UTC+8 解讀;停用排程不派工。

worker / scheduler 各自獨立啟動,指令見各模組 docstring(供 task-012 容器 command 使用)。
"""
