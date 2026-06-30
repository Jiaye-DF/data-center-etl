# sso-init — FastAPI 變體

> **本檔是 `sso-init` skill 的 FastAPI 變體**,由 [SKILL.md](./SKILL.md) 在使用者選「Python FastAPI」後分流進入;也可單獨閱讀執行。

在當前 FastAPI 專案中自動建立 DF-SSO 登入器所需的所有檔案（APIRouter、設定、HTTP client、HMAC 驗章）。
**執行前會詢問必要資訊；遇到使用者責任項目時必須明確停等或提醒。**

> 對應 [INTEGRATION.md](./INTEGRATION.md) 的 4 個端點設計：`/callback`、`/me`、`/logout`、`/back-channel-logout`。
> 預設 **FastAPI 0.110+ / Python 3.10+**,使用 `httpx.AsyncClient` + `pydantic-settings`。

## Agent 能力基線（跨 AI Model）

本 skill 是**模型無關**的執行指南,適用任何具備「讀檔 / 寫檔 / 執行 shell」能力的 AI agent（Claude Code / Codex / Cursor / Cline 等）。`INTEGRATION.md` 已隨本 skill 複製到同一層目錄；查契約時讀 `./INTEGRATION.md`,不要連到原專案的其他相對路徑。

- **Claude Code / 具備 AskUserQuestion 的 agent**:優先用互動式提問元件收集「詢問使用者」各項答案；沒有拿到答案前不得落檔。
- **Codex / 無互動式提問元件的 agent**:以純文字一次列出問題並停下等待回覆；收到回覆後再繼續寫檔與執行命令。
- **Cursor / Cline / 其他 agent**:若只能對話,也必須遵守同樣停等規則；若工具更強（plan mode / sub-agent / 多步驟表單）,只可**加強**遵守程度,不可降低。
- 「詢問使用者」與「需要使用者處理」兩節是**硬性停等點**:在使用者明確回覆前,**禁止**自行編造值、用 placeholder 帶過、或跳過往下執行。
- 若使用者要求「先產生檔案,憑證晚點補」,只允許 `SSO_APP_ID` / `SSO_APP_SECRET` 留空；`SSO_URL`、`APP_URL`、`APP_DIR` 仍須取得或由使用者明確接受預設。

## 詢問使用者（硬性停等,收到回覆才往下）

> 每一項都必須**實際問出口並等使用者回答**。**不可**自行假設或填預設值帶過。若 agent 的 UI 支援一次問多題,可以一次收集；若不支援,逐項詢問。

1. **SSO Backend URL** — 要接哪一個環境的 SSO 中央伺服器?**只提供正式站 / 測試站**,不要給本機 Dev 選項：
   - 正式站（Prod）：`https://df-it-sso-login.it.zerozero.tw`
   - 測試站（Test）：`https://df-sso-login-test.apps.zerozero.tw`
2. **App URL** — 當前專案對外的網址（例如 `https://warehouse.apps.zerozero.tw`）。**必問**,不要假設。
3. **App ID / App Secret** — 這兩個值由 **IT 發放**,agent 無法自行取得。先問使用者「是否已經跟 IT 告知要串接 DF-SSO?」:
   - **已告知並拿到** → 請使用者提供 `app_id` / `app_secret`,填進 `.env`。
   - **尚未告知 / 還沒拿到** → **可先跳過**,`.env` 的 `SSO_APP_ID` / `SSO_APP_SECRET` **留空**,其餘檔案照常產生;完成訊息務必提醒使用者「向 IT 申請後再回填」。
4. **App 目錄** — FastAPI 專案的 app 套件目錄（例如 `app`、`src`、`backend`）,預設 `app`。
5. **App Port** — 專案在本機開發時的 Port（例如 `8000`）。**若不是本機開發專案(只在部署環境跑),此題可略過**;略過時 `config.py` 的 `app_url` 預設值留 placeholder 即可,實際值由 `.env` 的 `APP_URL` 覆蓋。
6. **既有檔案衝突** — 若 `{APP_DIR}/sso/`、`main.py`、`.env`、`.gitignore` 已有同名檔或既有設定,必須列出衝突並詢問使用者要「整合既有內容」或「允許覆蓋」。預設行為是**整合既有內容、不覆蓋**。

## 需要使用者處理（agent 不能代勞）

下列項目 agent **無法自行完成**,必須明確提示使用者,並在最後的完成訊息中再列一次。若缺少任一項,仍可先完成程式碼落檔,但必須清楚標記「登入流程尚不能驗證完成」。

1. **向 IT 申請 `app_id` / `app_secret`** — 若 §「詢問使用者」#3 時尚未取得,整合完成後仍需使用者去跟 IT 申請,拿到再回填 `.env`。
2. **SSO Dashboard 白名單登記** — 由 IT 在對應環境的 Dashboard 把本專案 callback 的 origin（= App URL）登記進 `redirect_uris`,否則 SSO 會回 `redirect_uri is not registered`。
3. **回填留空的環境變數** — 若當下 `.env` 的 `SSO_APP_ID` / `SSO_APP_SECRET` 留空,登入流程在回填前無法實際運作。
4. **確認正式 App URL / callback origin** — 若使用者提供的是臨時網址或本機網址,必須提醒正式部署前要換成正式 App URL,並請 IT 重新確認白名單。
5. **決定哪些 API 要受保護** — agent 可示範 `Depends(require_auth)`,但哪些 business endpoints 要套登入與權限規則,必須由使用者或專案 owner 確認。

## 前置檢查

執行前先確認 `pyproject.toml` / `requirements.txt` 已含：

- [ ] `fastapi>=0.110`
- [ ] `httpx>=0.27`
- [ ] `pydantic>=2.0`
- [ ] `pydantic-settings>=2.0`
- [ ] `python-dotenv`（若要自動讀 `.env`）

若缺,請先補上：

```bash
pip install "fastapi>=0.110" "httpx>=0.27" "pydantic-settings>=2.0" python-dotenv
```

或在 `requirements.txt` 加上對應行。

## 執行步驟

假設使用者填入的 app 目錄為 `{APP_DIR}`(預設 `app`)。下列所有路徑都以此為基準。

### 1. 建立 `{APP_DIR}/sso/__init__.py`

```python
from .router import router as sso_router
from .config import sso_settings
from .deps import require_auth, SsoUser

__all__ = ["sso_router", "sso_settings", "require_auth", "SsoUser"]
```

### 2. 建立 `{APP_DIR}/sso/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class SsoSettings(BaseSettings):
    """DF-SSO 登入器設定,全部從環境變數讀取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sso_url: str = "http://localhost:3001"
    sso_app_id: str = ""
    sso_app_secret: str = ""
    app_url: str = "http://localhost:{使用者填的 Port}"
    sso_timeout_seconds: float = 8.0

    @property
    def is_secure(self) -> bool:
        """App 是否走 HTTPS（決定 cookie secure 旗標）。"""
        return self.app_url.startswith("https://")


sso_settings = SsoSettings()
```

### 3. 建立 `{APP_DIR}/sso/client.py`

```python
from typing import Any

import httpx

from .config import sso_settings


async def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    """所有 server-to-server 呼叫的共通 entry point。

    - 固定 timeout
    - 禁用 cache
    - 呼叫端負責判斷 status code
    """
    timeout = httpx.Timeout(sso_settings.sso_timeout_seconds)
    headers = kwargs.pop("headers", {}) or {}
    headers.setdefault("Cache-Control", "no-store")

    async with httpx.AsyncClient(base_url=sso_settings.sso_url, timeout=timeout) as client:
        return await client.request(method, path, headers=headers, **kwargs)


async def exchange(code: str) -> dict[str, Any] | None:
    """用 auth code 換 SSO token(帶 client_secret,server-to-server)。"""
    res = await _request(
        "POST",
        "/api/auth/sso/exchange",
        json={
            "code": code,
            "client_id": sso_settings.sso_app_id,
            "client_secret": sso_settings.sso_app_secret,
        },
    )
    if res.status_code != 200:
        return None
    return res.json()


async def me(token: str) -> tuple[int, dict[str, Any] | None]:
    """以 Bearer token 呼叫 SSO /me,回傳 (status_code, payload)。"""
    res = await _request(
        "GET",
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if res.status_code != 200:
        return res.status_code, None
    return 200, res.json()


async def logout(token: str, redirect_after: str) -> str | None:
    """通知 SSO 登出,並回傳 SSO 給的 Microsoft AD logout_url(含 id_token_hint
    + SSO post-logout 跳板)。Caller 必須把瀏覽器導去這個 URL,否則 AD 端
    SSO cookie 沒清掉,使用者 Refresh 會被靜默重新登入。

    redirect_after: AD 登出後最終要落地的 URL(必須在 sso_allowed_list)
    回傳: logout_url;SSO 不可達或 200 但缺欄位則回 None
    """
    try:
        res = await _request(
            "POST",
            "/api/auth/logout",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"redirect": redirect_after},
        )
        if res.status_code != 200:
            return None
        body = res.json()
        url = body.get("logout_url") if isinstance(body, dict) else None
        return url if isinstance(url, str) else None
    except Exception:
        return None
```

### 4. 建立 `{APP_DIR}/sso/security.py`

```python
import hashlib
import hmac
import time


MAX_TIMESTAMP_DRIFT_MS = 30_000  # 30 秒


def verify_back_channel_signature(
    user_id: str,
    timestamp: int,
    signature: str,
    app_secret: str,
) -> tuple[bool, str | None]:
    """驗 back-channel logout 的 HMAC 簽章。

    回傳 (is_valid, error_reason):
    - error_reason: "timestamp_expired" | "invalid_signature" | None
    - 使用 hmac.compare_digest 做 constant-time compare,
      對齊 SSO backend 的 crypto.timingSafeEqual。
    """
    now_ms = int(time.time() * 1000)
    if abs(now_ms - timestamp) > MAX_TIMESTAMP_DRIFT_MS:
        return False, "timestamp_expired"

    expected = hmac.new(
        app_secret.encode("utf-8"),
        f"{user_id}:{timestamp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
        return False, "invalid_signature"

    return True, None
```

### 5. 建立 `{APP_DIR}/sso/deps.py` — Auth Middleware（FastAPI Depends）

**整個整合的核心**。所有 protected endpoint（包含 `/me` 本身）都必須透過這個 `require_auth` dependency，才能保證「中央 session 被撤銷後下一次呼叫立即失效」。

```python
from typing import Any

from fastapi import Cookie, HTTPException, Response, status
from pydantic import BaseModel

from . import client


TOKEN_COOKIE = "token"


class SsoUser(BaseModel):
    userId: str
    email: str
    name: str
    erpData: dict[str, str] | None = None
    loginAt: str


def _clear_token_cookie(resp: Response) -> None:
    resp.delete_cookie(key=TOKEN_COOKIE, path="/")


async def require_auth(
    response: Response,
    token: str | None = Cookie(default=None),
) -> SsoUser:
    """Protected endpoint 入口都 Depends 這個。成功 → SsoUser；失敗 → HTTPException。

    no_token      → 401 + no_token（前端應自動導向 SSO）
    session_expired → 401 + session_expired + 清本地 cookie（前端顯示按鈕）
    sso_unreachable → 502（SSO 暫時不可達）
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "no_token"},
        )

    try:
        code, payload = await client.me(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "sso_unreachable"},
        )

    if code == 401:
        _clear_token_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "session_expired"},
        )
    if code != 200 or payload is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "sso_error"},
        )

    user_data: dict[str, Any] = payload.get("user") or {}
    return SsoUser(**user_data)
```

### 6. 建立 `{APP_DIR}/sso/router.py`

```python
import logging

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from . import client
from .config import sso_settings
from .deps import SsoUser, require_auth, TOKEN_COOKIE
from .security import verify_back_channel_signature


log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["sso"])

COOKIE_MAX_AGE = 24 * 60 * 60  # 24 小時


def _set_token_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key=TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=sso_settings.is_secure,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


def _clear_token_cookie(resp: Response) -> None:
    resp.delete_cookie(key=TOKEN_COOKIE, path="/")


# ---------- 1. OAuth callback ----------
@router.get("/callback")
async def callback(code: str | None = None) -> Response:
    """SSO 授權完成後的 callback:用 code 換 token,寫 cookie,導回 /dashboard。"""
    if not code:
        return RedirectResponse(url=f"{sso_settings.app_url}/?error=no_code", status_code=302)

    try:
        data = await client.exchange(code)
    except Exception as e:
        log.warning("[SSO] exchange failed: %s", e)
        return RedirectResponse(url=f"{sso_settings.app_url}/?error=exchange_error", status_code=302)

    if not data or not data.get("token"):
        return RedirectResponse(url=f"{sso_settings.app_url}/?error=exchange_failed", status_code=302)

    resp = RedirectResponse(url=f"{sso_settings.app_url}/dashboard", status_code=302)
    _set_token_cookie(resp, data["token"])
    return resp


# ---------- 2. /me（直接 Depends require_auth，一行 handler） ----------
@router.get("/me")
async def me(user: SsoUser = Depends(require_auth)) -> dict:
    """`/me` 本身就是 middleware 的第一個使用者,handler 只負責回 user。"""
    return {"user": user.model_dump()}


# ---------- 3. /logout ----------
@router.get("/logout")
async def logout(token: str | None = Cookie(default=None)) -> Response:
    """通知 SSO 登出,清自家 cookie,把瀏覽器導向 SSO 給的 AD logout_url。
    AD 清完自己的 SSO cookie 後會經 SSO post-logout 跳板回到 /?logged_out=1。
    取不到 logout_url 時 fallback 直接回首頁(此時 AD session 仍活著,
    使用者重新整理可能會被靜默重登)。
    """
    fallback = f"{sso_settings.app_url}/?logged_out=1"
    target = fallback
    if token:
        url = await client.logout(token, fallback)
        if url:
            target = url
    resp = RedirectResponse(url=target, status_code=302)
    _clear_token_cookie(resp)
    return resp


# ---------- 4. Back-channel logout ----------
class BackChannelPayload(BaseModel):
    user_id: str
    timestamp: int
    signature: str


@router.post("/back-channel-logout")
async def back_channel_logout(payload: BackChannelPayload, request: Request) -> Response:
    """SSO 廣播登出:驗 HMAC + timestamp drift 後清該 user 的本地 session。"""
    ok, reason = verify_back_channel_signature(
        user_id=payload.user_id,
        timestamp=payload.timestamp,
        signature=payload.signature,
        app_secret=sso_settings.sso_app_secret,
    )
    if not ok:
        status = 401 if reason in ("timestamp_expired", "invalid_signature") else 400
        return JSONResponse(status_code=status, content={"error": reason})

    log.info("[SSO] Back-channel logout user_id=%s", payload.user_id)
    # TODO: 清掉該 user 在本 App 的 server-side session(若有,例如 Redis / DB session store)
    return JSONResponse(status_code=200, content={"success": True})
```

### 7. 在 `main.py` 掛上 router

找到 FastAPI 專案的入口(通常是 `{APP_DIR}/main.py` 或 `main.py`),加上：

```python
from fastapi import FastAPI
from {APP_DIR}.sso import sso_router

app = FastAPI()

# ... 原本的其他 routes ...
app.include_router(sso_router)
```

> 若是 `src/main.py` 結構,import 路徑要調成 `from src.sso import sso_router`。
> 若尚未建立 `main.py`,請同步建立一個最小骨架(不覆蓋既有檔案)。

### 8. 建立或更新 `.env`

在專案根目錄 `.env` **追加**下列環境變數(不覆蓋原有內容)：

```
# DF-SSO 登入器
SSO_URL={使用者填的 SSO URL}
SSO_APP_ID={使用者填的 App ID;IT 尚未發放則留空}
SSO_APP_SECRET={使用者填的 App Secret;IT 尚未發放則留空}
APP_URL={使用者填的 App URL}
```

> ⚠️ 若 §「詢問使用者」#3 使用者尚未向 IT 取得憑證,`SSO_APP_ID` / `SSO_APP_SECRET` **留空**即可(`config.py` 預設值為空字串,不會壞);其餘檔案照常產生,待 IT 發放後回填這兩行。
> ⚠️ `SSO_APP_SECRET` **絕不可** commit 進 git,也不可透過任何前端 bundler 暴露出去。
> ⚠️ `.env` 的變數名必須是大寫,pydantic-settings 會自動映射到 `SsoSettings` 的小寫欄位。

同步更新 `.gitignore`(若尚未含):

```
.env
.env.local
.env.*.local
```

### 9. 顯示完成訊息

告知使用者：

```
✅ SSO 登入器整合完成（Python FastAPI）!

已建立的檔案：
  {APP_DIR}/sso/__init__.py
  {APP_DIR}/sso/config.py
  {APP_DIR}/sso/client.py
  {APP_DIR}/sso/security.py
  {APP_DIR}/sso/deps.py    — require_auth FastAPI Depends（auth middleware）
  {APP_DIR}/sso/router.py  — 4 個端點，/me 一行 Depends(require_auth)
  main.py — 已掛上 sso_router
  .env — 已追加 SSO 環境變數

📋 接下來你需要（agent 無法代勞,請自行處理）：

1. 向 IT 申請 / 確認 SSO 憑證與白名單：
   - 若還沒跟 IT 說要串接 → 先告知 IT,申請本環境的 app_id / app_secret
   - 請 IT 在對應環境的 SSO Dashboard 把 callback 的 origin 登記進 redirect_uris 白名單:
     {使用者填的 App URL}
   - 拿到 app_id / app_secret 後,回填 .env 的 SSO_APP_ID / SSO_APP_SECRET
   - 若目前使用的是本機或臨時 App URL,正式部署前要改成正式 App URL,並請 IT 重新確認白名單
   ⚠️ 目前 .env 的 SSO_APP_ID / SSO_APP_SECRET 若留空,登入流程在回填前無法運作

2. 所有需要登入的 protected endpoint 一律 Depends(require_auth)：

   from fastapi import APIRouter, Depends
   from {APP_DIR}.sso import require_auth, SsoUser

   router = APIRouter()

   @router.get("/api/assets")
   async def list_assets(user: SsoUser = Depends(require_auth)):
       # user 保證已登入；每次呼叫都已向中央 Redis 確認 session
       return {"viewer": user.email, "assets": []}

3. 需要 role/權限檢查時，在 endpoint 內拿 user 繼續判斷：

   @router.get("/api/reports")
   async def reports(user: SsoUser = Depends(require_auth)):
       if not user.email.endswith("@df-recycle.com"):
           raise HTTPException(status_code=403, detail="forbidden")
       return {...}

4. 啟動 FastAPI 驗證端點：
   uvicorn {APP_DIR}.main:app --reload --port {使用者填的 Port}
   curl http://localhost:{使用者填的 Port}/api/auth/me  # 應該回 401 no_token

5. 在你的登入頁（React / Vue / Jinja 都可）加上按鈕：

   const SSO_URL = "{使用者填的 SSO URL}";
   const APP_URL = "{使用者填的 App URL}";
   const APP_ID  = "{使用者填的 App ID}";

   const ssoUrl = `${SSO_URL}/api/auth/sso/authorize`
     + `?client_id=${encodeURIComponent(APP_ID)}`
     + `&redirect_uri=${encodeURIComponent(APP_URL + "/api/auth/callback")}`;

   <button onClick={() => window.location.href = ssoUrl}>透過 DF-SSO 登入</button>

6. 登出按鈕：

   <a href="/api/auth/logout">登出</a>
```

## 注意事項

- **Async vs sync**:`httpx.AsyncClient` 對齊 FastAPI 的 async-first 設計。若你的專案是純同步(例如 Flask 或用 `def` 而不是 `async def`),把 `httpx.AsyncClient` 換成 `httpx.Client`、把 router 的 `async def` 改成 `def`,其他邏輯完全一樣
- **Cookie secure 旗標**:`SsoSettings.is_secure` 依 `app_url` 協定自動決定;Prod `https://` 會自動打開,本機 `http://` 不會(否則瀏覽器不會送 cookie)
- **SameSite**:固定 `Lax`,對齊 [INTEGRATION.md](./INTEGRATION.md)。跨 domain iframe 嵌入才需 `None`+`Secure`
- **`no_token` vs `session_expired`**:這個區分務必保留。前端看到 `no_token` 要自動導向 SSO(跨 App 免登入體驗),看到 `session_expired` 要顯示按鈕避免無限重導
- **back-channel logout 的 TODO**:若你用 Redis / DB 存 server-side session,在 `back_channel_logout` 裡要實際去清該 `user_id` 的 session,不然只是回 200 並沒有真的登出本地
- **HMAC constant-time compare**:`hmac.compare_digest` 是 Python 標準函式庫內建的 constant-time 比對,對齊 SSO backend 的 `crypto.timingSafeEqual`
- **pydantic-settings 版本**:範例用 Pydantic v2 的 `pydantic-settings`。若卡在 Pydantic v1,請改成 `from pydantic import BaseSettings` 並移除 `SettingsConfigDict`
- **HTTPX connection reuse**:為簡化,每次呼叫都新開 `AsyncClient`。若 SSO 呼叫量很大想共用連線池,可在 FastAPI `lifespan` 裡建立單一 `AsyncClient` 並注入,不影響本 skill 的其他邏輯
- 若 `{APP_DIR}/sso/` 目錄已存在同名檔案,詢問使用者是否覆蓋
