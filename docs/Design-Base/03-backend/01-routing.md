# 01-routing — 路由 + 統一回應

> **何時讀**:寫新 endpoint 才讀。

## API 路由

- 統一前綴 `/api/v1`
- kebab-case 複數(`/api/v1/user-groups`)
- 路徑參數用 UID(UUID),**禁**用內部主鍵
- 多層最多兩層(`/api/v1/users/{uid}/roles`)
- 動作型用動詞後綴(`POST /api/v1/users/{uid}/disable`)

## 版本化

- 預設 `/api/v1`;向下相容功能 → 視情況開 `/api/v1.1`(minor);breaking → 開 `/api/v2`(major)
- 路徑版本最細到 **minor**(`v1` / `v1.1` / `v2` / `v3`),**禁** patch(bug fix 不換路徑,走 commit + `fixed.md`)
- bump major / minor 判準 → `01-propose/05-version-bump.md § breaking change 判定`
- v1 → v2 切換,v1 留 **≥ 1 個 minor 棄用期**(對齊 `05-version-bump.md § 版本停用`)

> 開 minor 路徑(`v1.1`)等於對外承諾**同時維護 v1 與 v1.1**。若不需分流,新 endpoint 直接掛在 `v1` 內即可;`v1.1` 只在「想隔離行為差異 / 讓 client 鎖版」時才開。

## 統一回應外殼

```python
class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    detail: str | None = None
    response_code: int
```

- `data`:`null` 或 dict;**禁**直接為 array(列表須 `{items: [...], total}`)
- `detail`:使用者可讀訊息;**禁**洩漏 SQL / traceback / 內部欄位
- `response_code`:int,**等同 HTTP status**(細節見下節)
- 路由 response type **必**用 Pydantic schema;**禁** `dict` / `dict[str, object]`

例外:檔案下載(`StreamingResponse`)豁免外殼;錯誤仍走標準 HTTP status + ApiResponse。

## 狀態碼

`ApiResponse.response_code` **必**等於 HTTP status code。前端 RTK Query 靠 status code 分流(401 → 重登、404 → not found、409 → 衝突),**禁** `200 + success: false` 掩蓋錯誤。

### Success(2xx)

| code | 用途 |
| --- | --- |
| **200** OK | GET / PATCH / 動作型 POST(非 create) / DELETE 軟刪 |
| **201** Created | POST 建立資源(`data` 帶新建 entity) |
| **204** No Content | 罕用(`ApiResponse` 通常帶 body);僅 file 類無回應場景 |

### Error(4xx / 5xx)

| code | 用途 | 例 |
| --- | --- | --- |
| **400** Bad Request | 商業邏輯違規(非 schema 錯誤) | 餘額不足、訂單已關閉、狀態機禁止轉換 |
| **401** Unauthorized | 未登入 / token 無效 / 過期 | JWT 過期、缺 `Authorization` header |
| **403** Forbidden | 已登入但無權限 | 角色不足、跨 user 偷資源 |
| **404** Not Found | 資源不存在(含 soft-deleted) | UID 找不到、`is_deleted=true` |
| **409** Conflict | 唯一鍵 / 樂觀鎖衝突 | email 重複、`updated_at` 版本衝突 |
| **422** Unprocessable Entity | **FastAPI 自動回** schema 驗證失敗 | Pydantic 解析失敗 |
| **429** Too Many Requests | rate limit | 對齊 `90-third-party-service/02-rate-and-cost.md` |
| **500** Internal Server Error | 未捕獲例外 | 業務錯誤**禁**主動 raise 500 |

### 禁忌

- **禁** `return 200 + ApiResponse(success=False)` — error 必走真實 4xx
- **禁**手動 `raise HTTPException(status_code=422, ...)`(讓 Pydantic 自動處理 schema 錯誤)
- **禁**業務層主動 `raise HTTPException(500, ...)` — 找不到對應 4xx 就重新檢視錯誤分類
- **禁** 401 ↔ 403 混用(401 = 不知你是誰;403 = 知道但不准)
- **禁**用 200 + `detail` 表達 partial failure — 拆成多個 endpoint 或回 207 / 4xx
