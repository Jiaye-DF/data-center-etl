---
id: task-003
title: DF-SSO 後端整合(雙軌登入之 SSO 側)
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/api/v1/sso.py
  - backend/app/api/v1/__init__.py
  - backend/app/clients/df_sso.py
  - backend/app/services/sso_service.py
  - backend/app/core/config.py
  - backend/tests/test_sso.py
estimated_hours: 3
---

## 目標

接公司 DF-SSO 中央登入器(callback / me / logout / back-channel-logout 四端點),SSO 使用者對應到自有 `users` 表與角色(首次登入自動建 viewer,升 admin 由管理者改);與 task-002 的本地登入**共用**同一 session cookie 機制,前端登入頁屬 task-009。

## 範圍要點

- 落檔走 `sso-init` skill(FastAPI 變體),契約遵循 `90-third-party-service/08-df-sso.md` 四硬性契約。
- SSO client 置於 `app/clients/df_sso.py`(httpx + timeout / 錯誤轉 AppError,`03-backend/06-clients.md`)。
- SSO 設定(base url / client id / secret)走 env 進 Settings;**禁**硬編。
- **互鎖註記**:`api/v1/__init__.py` 由 task-002 建立匯集,本 task 序列化在後(`parallel: false`)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_sso.py -q` 全綠(callback 換 token(respx mock)/ 首次登入建 user(role=viewer)/ 重複登入不重建 / back-channel logout 使 session 失效)
- [ ] `! grep -nE "(client_secret|CLIENT_SECRET)\s*[:=]\s*['\"]" backend/app` 成立(無硬編機密)
- [ ] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/90-third-party-service/00-overview.md` + `01-client-design.md`(永遠讀)
- `docs/Design-Base/90-third-party-service/08-df-sso.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/06-clients.md`
- `docs/Design-Base/03-backend/07-testing.md`(respx)
