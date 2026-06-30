# 08-performance — 後端效能

> **何時讀**:效能優化任務 / N+1 / async 阻塞排查才讀。

主題:**N+1**、**async 阻塞**、**event loop 飢餓**、**大 JSON parse**、**連線池耗盡**。

---

## N+1(資料庫)

```python
# ❌ 在 loop 裡 query
for user in users:
    user.groups = await group_repo.list_by_user(user.uid)   # N 次

# ✅ 預載
stmt = select(User).options(selectinload(User.groups))
users = (await db.execute(stmt)).scalars().all()
```

對齊 `04-databases/09-indexes-and-perf.md`:

- 一對多 → `selectinload`(分兩次 query 但無 JOIN 爆量)
- 多對一 / 一對一 → `joinedload`
- N+1 偵測:`SQLAlchemy` log SQL 開發時觀察 / 用 `sqltap`

## async 阻塞

```python
# ❌ async 函式內呼叫 sync 重 IO / CPU
async def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()  # 同步 + CPU 重

# ✅ 走 to_thread
async def hash_password(plain: str) -> str:
    return await asyncio.to_thread(_bcrypt_hash, plain)
```

阻塞操作清單(都需 `to_thread`):

- `bcrypt.hashpw` / `bcrypt.checkpw`
- `Pillow` / `numpy` 大計算
- 大檔案 `open(..., 'r').read()`(對齊 `aiofiles` 替代)
- 第三方 sync SDK(無 async API)

## Event loop 飢餓

```python
# ❌ tight loop 不讓 event loop 跑
async def crunch(n: int) -> int:
    s = 0
    for i in range(n):              # n 大 → 這個 task 占滿 thread
        s += i
    return s

# ✅ 適時 yield
async def crunch(n: int) -> int:
    s = 0
    for i in range(n):
        s += i
        if i % 10_000 == 0:
            await asyncio.sleep(0)  # yield 一次
    return s
```

CPU 重邏輯走 `to_thread` 或拆 batch worker(避免擋住 event loop;同 worker 其他 request 變慢)。

## 大 JSON parse

第三方回 MB 級 JSON → 預設 `response.json()` 一次 load 進記憶體 + parse:

```python
# ❌ 大檔一口氣 load
data = response.json()

# ✅ stream + 分段
async with httpx.AsyncClient() as client:
    async with client.stream("GET", url) as r:
        async for chunk in r.aiter_bytes(chunk_size=64 * 1024):
            ...
```

或用 `ijson`(stream JSON parser,加進 `01-versions.md` 後使用)。

## 連線池耗盡

```python
# ✅ 配置
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,    # 30 分回收(避免 idle connection 被中介設備斷)
)
```

對齊 `04-databases/07-connection.md`:

- `pool_size` ≥ uvicorn worker 數 × 應用內並行(預估)
- 監控 `pool_timeout` 觸發 → 連線不夠或 leak
- AsyncSession **必**用 `async with`,**禁**手動管理(忘 close 會 leak)

## httpx 連線池

```python
# ✅ lifespan 級單例
self._http = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
    timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
)
```

對齊 `90-third-party-service/01-client-design.md`:

- **禁**每 request 開新 client(無 keepalive,握手成本)
- 並發高 → `max_connections` 調大,但別超第三方 rate limit

## Profile 工具

- `py-spy`:正在跑的 process profiling(`py-spy top --pid <PID>`)
- `cProfile`:單 request profiling
- `asyncio` debug mode:`PYTHONASYNCIODEBUG=1` 偵測 task 慢
- Sentry Performance:對齊 `90-third-party-service/06-monitoring.md`

## 衡量

- 改前 / 改後寫進 PR description:p50 / p95 / RPS / RAM
- 微優化(< 10% 改善)+ 增加複雜度 → **不**做(對齊 `99-code-review/05-performance-checklist.md`)
- 衡量數據要可重現(同 hardware / 同 dataset / 同並發數)

## 不要做

- ❌ 把同步 lib 包進 `loop.run_in_executor` 又忘記退場(thread pool 滿)
- ❌ async 函式內 `time.sleep()`(blocking)→ `await asyncio.sleep()`
- ❌ 為了「快」改寫成 sync(整個棧 async,sync 反而需要 to_thread,慢更多)
- ❌ 預設認為慢 = DB 慢(可能是 N+1、可能是 lock、可能是 GIL — 先 profile)
