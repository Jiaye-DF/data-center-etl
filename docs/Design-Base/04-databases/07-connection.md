# 07-connection — 連線管理

> **何時讀**:改連線設定才讀。

- **必** `create_async_engine` + `async_sessionmaker`;**禁**每請求建立新連線
- 連線池參數透過 env(`pool_size` / `max_overflow` / `pool_recycle`)
- graceful shutdown 須 `await engine.dispose()`(放 lifespan shutdown,見 `03-backend/04-config.md`)
