# 04-sso-azure-ad — Azure AD SSO

> **何時讀**:做 Azure AD 單一登入才讀。對應前端規則見 `02-frontend/03-env-and-auth.md`。

OAuth 2.0 Authorization Code + PKCE 流程,後端走 MSAL 或自寫;客戶端 secret 留後端。

---

## env 設定

```
AZURE_AD_TENANT_ID=<tenant-uuid>
AZURE_AD_CLIENT_ID=<app-uuid>
AZURE_AD_CLIENT_SECRET=<runtime-injected>     # 機密
AZURE_AD_REDIRECT_URI=https://api.<domain>/api/v1/auth/azure/callback
AZURE_AD_SCOPES=openid profile email User.Read
AZURE_AD_AUTHORITY=https://login.microsoftonline.com/${AZURE_AD_TENANT_ID}
```

對齊 `00-overview/02-secrets.md`:`AZURE_AD_CLIENT_SECRET` 為機密。

## 流程(後端為主)

```
1. user click「以 Azure 登入」
   → 前端打 GET /api/v1/auth/azure/login
2. 後端產 state(CSRF token)+ PKCE verifier,存 cookie / redis,
   回傳 redirect URL → user 被導去 Microsoft 登入
3. 認證成功 → Microsoft redirect 回 /api/v1/auth/azure/callback?code=...&state=...
4. 後端驗 state(對齊 cookie)+ 用 code + verifier 換 token
5. 解 id_token JWT → 抓 claims(email / oid / name)
6. 對照 / 建立 user → 簽 session JWT → set httpOnly cookie
7. redirect 前端 /dashboard
```

## state CSRF + PKCE(必)

```python
import secrets, hashlib, base64

def gen_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge

@router.get("/auth/azure/login")
async def azure_login(response: Response) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    verifier, challenge = gen_pkce()
    response.set_cookie("azure_state", state, httponly=True, secure=True, samesite="lax", max_age=600)
    response.set_cookie("azure_verifier", verifier, httponly=True, secure=True, samesite="lax", max_age=600)
    url = (
        f"{settings.AZURE_AD_AUTHORITY}/oauth2/v2.0/authorize"
        f"?client_id={settings.AZURE_AD_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={settings.AZURE_AD_REDIRECT_URI}"
        f"&response_mode=query"
        f"&scope={settings.AZURE_AD_SCOPES}"
        f"&state={state}"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=S256"
    )
    return RedirectResponse(url)
```

callback:

```python
@router.get("/auth/azure/callback")
async def azure_callback(
    code: str,
    state: str,
    request: Request,
    response: Response,
    azure: AzureAdClient = Depends(get_azure_ad_client),
    auth_service: AuthService = Depends(),
) -> RedirectResponse:
    # 1. 驗 state
    if state != request.cookies.get("azure_state"):
        raise AzureAdAuthError("state mismatch (CSRF)")
    verifier = request.cookies.get("azure_verifier")
    if not verifier:
        raise AzureAdAuthError("missing PKCE verifier")
    # 2. 換 token
    tokens = await azure.exchange_code(code=code, verifier=verifier)
    # 3. 驗 id_token + 抓 claims
    claims = await azure.verify_id_token(tokens.id_token)
    # 4. upsert user
    user = await auth_service.upsert_from_azure(claims)
    # 5. 簽 session JWT + set cookie
    session_token = auth_service.issue_session(user)
    response.set_cookie("session", session_token, httponly=True, secure=True, samesite="lax", max_age=86400)
    response.delete_cookie("azure_state")
    response.delete_cookie("azure_verifier")
    return RedirectResponse(settings.FRONTEND_AFTER_LOGIN_URL)
```

## id_token 驗證

**必**驗:

- 簽章(用 Microsoft 公開 JWKS,快取 1 小時)
- `iss`(=`https://login.microsoftonline.com/<tenant>/v2.0`)
- `aud`(=`AZURE_AD_CLIENT_ID`)
- `exp` / `nbf`
- `tid`(=`AZURE_AD_TENANT_ID`,防其他租戶偽造)

**禁**只解碼不驗(任何人可偽造 base64)。用 `pyjwt[crypto]`(對齊 `00-overview/01-versions.md`)。

## Claims mapping

對應到我方 user 表:

| Azure claim | 對應欄位 |
| --- | --- |
| `oid`(物件 ID) | `users.azure_oid`(unique) |
| `email` / `preferred_username` | `users.email` |
| `name` | `users.display_name` |
| `tid` | 驗證用,**不**存 |

`oid` 為穩定 ID(user 改 email / name 不變),作為唯一鍵。

## 登出

對齊 RP-Initiated Logout:

```
GET /api/v1/auth/logout
→ 後端清 session cookie
→ redirect 至 https://login.microsoftonline.com/<tenant>/oauth2/v2.0/logout?post_logout_redirect_uri=...
```

## 不要做

- ❌ 把 `id_token` 存 DB(短期 token,每次重新驗即可)
- ❌ 用 `access_token` 當作我方 session(走我方 JWT,access_token 只用來打 Microsoft Graph)
- ❌ 跳過 state / PKCE 驗證(CSRF / interception 攻擊面)
- ❌ 把 `client_secret` 放前端(對齊 `02-frontend/03-env-and-auth.md`)
