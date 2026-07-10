# manual-removal-checklist — `users.role` 字串欄位 + `ck_users_role` 約束

> v1.4.1 起 `roles` 表(`users.role_pid` FK)為角色唯一事實來源;既有 `users.role`
> 字串欄位與 `ck_users_role` CheckConstraint **原樣保留、標記 deprecated**,依
> CLAUDE.md「禁任何 DROP 類資料庫操作」不可由 migration 自動移除。本清單記錄
> 未來人工移除該欄位 / 約束前必須確認的前置條件與步驟。

## 前置條件(缺一不可移除)

1. **task-002 落地**:授權鏈路(guards / `auth.me` / `sso.me`)已全面改讀
   `users.role_pid → roles.code`,不再讀 `users.role` 字串欄位。
2. **task-003 落地**:角色指派 API 寫入路徑已全面改寫 `role_pid`,`users.role`
   字串欄位不再被任何寫入路徑更新(dual-write 註記結束)。
3. **`role_pid` 已收 NOT NULL**:對齊 `fixed.md §1` 的後續事項 —
   task-002 落地後應有一支後續 migration 幫 `role_pid` 收 NOT NULL;
   確認該 migration 已上線且 `SELECT count(*) FROM users WHERE role_pid IS NULL` = 0。
4. **全文檢索確認無殘留讀取**:於 repo 執行
   `grep -rn "\.role\b" backend/app --include="*.py"`(排除 `role_pid` / `role_ref` /
   `Role` model 本身),確認所有命中皆非讀取 `User.role` 字串欄位語意
   (含 `app/api/v1/auth.py`、`app/api/v1/sso.py`、`app/services/sso_service.py`
   目前已知讀取點,見下方清單)。
5. **前端無殘留依賴**:確認前端(`frontend/src`)API 回應型別與畫面渲染邏輯
   皆改依角色 API(task-003/004)取得角色資訊,不再依賴登入回應中的舊
   `role` 欄位語意(即使欄位名稱不變,語意來源需已切換為 `role_pid` 衍生值)。

## 目前已知讀取 / 寫入 `users.role` 字串欄位的位置(task-001 當下快照)

- 讀取:`backend/app/api/v1/auth.py`(`role=user.role`,回應序列化)、
  `backend/app/api/v1/sso.py`(同上)、`backend/app/services/sso_service.py`
  (`create_sso_access_token` 的 JWT payload `"role": user.role`)
- 寫入:`backend/app/repositories/user_repo.py`(`UserRepository.create()`)、
  `backend/app/services/auth_service.py`(`ensure_init_admin` 建立 admin)、
  `backend/app/services/sso_service.py`(`_get_or_create_user` 建立 viewer)
- 約束:`ck_users_role`(`backend/app/models/user.py` `__table_args__`)

> 上述清單會隨 task-002 / task-003 落地而清空;移除前請重新跑一次全文檢索
> 確認清單已歸零,而非直接沿用本清單。

## 移除步驟(前置條件全數滿足後才執行)

1. 開新 migration(`v{N}_remove_users_role_string.py`),**僅**在該版本明確決議
   移除時才建立(本清單本身不預先建立該 migration)。
2. migration 內容:
   - `op.drop_constraint("ck_users_role", "users", type_="check")`
   - `op.drop_column("users", "role")`
   - 此為本清單明確授權之**唯一**允許對 `users.role` 做 DROP 的時機
     (CLAUDE.md 禁 DROP 為預設底線;此處為版本決議後的例外流程,需在
     该 migration docstring 與對應 task 檔 / fixed.md 明確記錄決議依據)。
3. 同步移除 `backend/app/models/user.py` 的 `role` 欄位定義與
   `ck_users_role` 之 `CheckConstraint`。
4. 同步移除本檔案列出的所有讀取 / 寫入點殘留程式碼(若尚未在 002/003 移除)。
5. 更新本檔案:於檔尾加註「已於 v{X.Y.Z} 移除,見 commit `<hash>`」,
   不刪除本檔案(歷史留痕)。
