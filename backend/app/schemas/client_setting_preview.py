"""API Client 最終可見欄位預覽 schema(v1.6.1 task-007)。

回應核心為 `operations[].tables`,形狀等價於 propose 的 `{作業: {表: {欄位: read/edit}}}`;
作業另帶 uid / 服務代碼供前端定位(作業名僅在服務內唯一,不可當全域 key)。
`role` / `exception_sets` 為預覽脈絡(這些權限從哪來),非權限計算結果本身。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EffectiveRoleSummary(BaseModel):
    """Client 目前指派的角色(0..1);未指派時整個欄位為 null。"""

    uid: UUID = Field(description="角色公開識別碼")
    name: str = Field(description="角色名稱")
    permission_profile_uid: UUID | None = Field(
        default=None, description="綁定的角色權限設定檔識別碼(角色權限設定檔已刪除時為 null)"
    )
    permission_profile_name: str | None = Field(
        default=None, description="綁定的角色權限設定檔名稱(角色權限設定檔已刪除時為 null)"
    )


class EffectiveExceptionSetSummary(BaseModel):
    """納入計算的臨時權限組(僅未過期綁定;已過期一律不出現)。"""

    uid: UUID = Field(description="臨時權限組公開識別碼")
    name: str = Field(description="臨時權限組名稱")
    expires_at: datetime | None = Field(
        default=None, description="綁定效期(UTC+8 naive;null = 不設限)"
    )


class EffectiveOperationPermission(BaseModel):
    """單一作業的最終可見欄位;`tables` 為空 = 作業有開門但無欄位授權(default-closed)。"""

    operation_uid: UUID = Field(description="作業公開識別碼")
    operation_name: str = Field(description="作業名稱(僅在服務內唯一)")
    service_code: str = Field(description="所屬服務代碼(erp / crm…)")
    tables: dict[str, dict[str, str]] = Field(
        description=(
            "最終可見欄位 `{表: {欄位: read/edit}}`(授權 ∩ 作業範圍;"
            "交集為空的表整張省略,欄位 `*` = 該表全欄位;"
            "`*` 與具名欄位並存時,具名欄位為更高權限的覆寫 —— "
            "動作不高於 `*` 的具名欄位一律收斂省略)"
        )
    )


class EffectivePermissionsResponse(BaseModel):
    """單一 API Client 的最終權限預覽(角色綁定的角色權限設定檔 ∪ 未過期臨時權限,再 ∩ 作業範圍)。"""

    client_uid: UUID = Field(description="API Client 公開識別碼")
    role: EffectiveRoleSummary | None = Field(
        default=None, description="指派的角色(未指派為 null)"
    )
    exception_sets: list[EffectiveExceptionSetSummary] = Field(
        description="納入計算的臨時權限組(未過期;無則空陣列)"
    )
    operations: list[EffectiveOperationPermission] = Field(
        description="有授權入口的作業(依服務代碼 + 作業名排序;無角色無臨時權限則空陣列)"
    )
