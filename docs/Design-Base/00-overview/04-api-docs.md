# 04-api-docs — API 文件 + 路徑

> **何時讀**:寫 FastAPI 入口 / 新增 endpoint 時讀。本檔定義**對外路徑 + OpenAPI metadata 底線**;`ApiResponse` 殼 / 路由細節見 `03-backend/01-routing.md`,例外回應 schema 見 `03-backend/05-exceptions-and-logging.md`。

---

## 路徑

- FastAPI **必**:`docs_url="/api/docs"`、`redoc_url=None`、`openapi_url="/api/openapi.json"`
- **禁用**:`/swagger`、`/docs`、`/openapi`(避開常見掃描路徑 + path collision)
- 路由前綴 `/api/v1/...`;向下相容功能 → 視情況開 `/api/v1.1/...`(minor),breaking → 開 `/api/v2/...`(major),**禁**版本混塞於同一前綴(細節見 `03-backend/01-routing.md § 版本化`)

## 環境暴露

| | development | staging | production |
| --- | --- | --- | --- |
| `/api/docs` | 開 | 開 | 預設開(內網 API);若公網 → 加保護 |
| `/api/openapi.json` | 同 `/api/docs` | 同 | 同 |

production 若需保護:於反向代理層(Coolify / nginx)擋 IP / Basic auth,**禁**讓未認證使用者直接打。

## OpenAPI metadata 必填

新增 / 修改 endpoint 時 router 必標:

```python
@router.get(
    "/user-groups",
    response_model=UserGroupListResponse,
    summary="取得使用者群組清單",
    tags=["user-groups"],
)
```

- `response_model=` 必為 Pydantic schema(**禁** `dict` / 無 type / `Any`,細節見 `03-backend/01-routing.md`)
- `summary=` 一句話中文描述
- `tags=` 用 kebab-case 資源名,**與路徑對齊**(`/api/v1/user-groups` → `tags=["user-groups"]`)
- OpenAPI 標的 `status_code=` 必跟路由實際回傳對齊;狀態碼對照表(2xx / 4xx / 5xx)見 `03-backend/01-routing.md § 狀態碼`

## Pydantic schema 欄位 metadata

- `Field(..., description="<語意>")` **必填**;空字串視為缺漏
- 有典型輸入 / 輸出值 → 加 `examples=[...]`(供 `/api/docs` Try it out)
- 列舉值用 `Enum`,**禁** `Literal["a","b"]` 散落

```python
class UserCreateRequest(BaseModel):
    email: EmailStr = Field(..., description="登入帳號 email", examples=["alice@example.com"])
    role: UserRole = Field(..., description="角色")
```

## OpenAPI 產出 / 同步

- `/api/openapi.json` 由 FastAPI 自動產;**禁**手刻 OpenAPI yaml
- 前端若需 client codegen → CI 跑 `curl /api/openapi.json > frontend/openapi.json` 並比對 diff;**禁** commit 過時版本
- API 新增 / 改動 → schema 變動 → 對應 frontend RTK Query endpoints 同步(由前端任務跟進)

## 第三方 API 文件

第三方 API client 內部文件(SMTP / SSO / payment)放於 `app/clients/<service>/README.md`;本檔不負責,見 `90-third-party-service/`。
