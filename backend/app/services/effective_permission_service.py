"""API Client 最終可見欄位展開(v1.6.1 task-007)。

計算語意對齊 `docs/Arch/datahub-api-gateway-arch.html` 模組②③「三情境對照」,**此展開即
模組③ 的權限語意前哨**,後續每請求判斷路徑直接沿用本檔:

- 授權來源 = **Role 綁定的設定檔 ∪ 未過期的特例權限組**(加法模型,只授予、無 deny)。
- **default-closed**:作業要「被勾選(開門)」**且**「該作業下有表欄位授權」才看得到欄位;
  勾了作業卻沒給授權 → 該作業回空 `tables`(有入口、無欄位),缺一不可。
- 授權項再 ∩ 作業範圍(`operation_items`):範圍外的表 / 欄位一律不生效;`*` 依範圍展開為
  該表全欄位(範圍本身為 `*` 時無具體欄位清單可展開,原樣保留 `*` 代表全欄位)。
- 同欄位多筆授權取較高動作(`edit` 隱含 `read`);同一張表 `*` 與具名欄位並存時,具名欄位
  只在動作**高於** `*` 時保留(具名 = `*` 的更高權限覆寫),其餘一律收斂進 `*`。
- 「開門」與「授權」的配對**以授權來源為單位**判定(設定檔一組、每個特例組各一組),
  避免 A 來源開門、B 來源給欄位被拼裝成雙方都沒真正授予的權限;各來源結果再聯集。
- 效期比較走 naive UTC+8(`04-databases/06-timezone.md`),過期特例由 repo 層直接濾掉。

讀取走 task-003 快取(`client_setting:effective:<client_uid>`,TTL 兜底,Redis 故障降級直讀)。
快取內容含 Role / 特例組名稱與效期:名稱改名、以及「快取後才到期」的特例,最遲於 TTL
到期收斂(權限內容本身的異動由寫入端 commit 後即刻失效快取)。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.api_client_user import ApiClientUser
from app.models.client_setting import ACTION_EDIT, ACTION_READ, ALL_COLUMNS
from app.repositories.client_setting_repo import (
    ClientSettingRepository,
    client_setting_session,
)
from app.schemas.client_setting_preview import (
    EffectiveExceptionSetSummary,
    EffectiveOperationPermission,
    EffectivePermissionsResponse,
    EffectiveRoleSummary,
)
from app.services import permission_cache

_CLIENT_NOT_FOUND_DETAIL = "API Client 不存在"

# 動作強弱:edit 隱含 read,同欄位取較高者
_ACTION_RANK: Final[dict[str, int]] = {ACTION_READ: 0, ACTION_EDIT: 1}

# 單筆授權項:作業 pid × 表 × 欄位 × 動作(設定檔 / 特例組共用同一形狀)
type _GrantRow = tuple[int, str, str, str]
# 一個授權來源:(該來源開門的作業 pid, 該來源的授權項)
type _GrantSource = tuple[set[int], list[_GrantRow]]


def _higher_action(current: str | None, candidate: str) -> str:
    if current is None:
        return candidate
    if _ACTION_RANK.get(candidate, 0) > _ACTION_RANK.get(current, 0):
        return candidate
    return current


def _collapse_all_columns(columns: dict[str, str]) -> dict[str, str]:
    """同一張表同時出現 `*` 與具名欄位時收斂(v1.6.1 fixed AD-155)。

    `*` 已涵蓋全欄位,故具名欄位只有在**動作更高**(`*` read + 具名 edit)時才有意義,
    否則一律剔除 → 契約明確化為「具名欄位是 `*` 的更高權限覆寫」,消費端不必自行猜優先權。
    """
    star = columns.get(ALL_COLUMNS)
    if star is None:
        return columns
    return {
        column: action
        for column, action in columns.items()
        if column == ALL_COLUMNS
        or _ACTION_RANK.get(action, 0) > _ACTION_RANK.get(star, 0)
    }


def _effective_columns(scope_columns: set[str], column: str) -> list[str]:
    """授權欄位 ∩ 作業範圍;`*` 依範圍展開,超出範圍回空集合(該授權項不生效)。"""
    if not scope_columns:
        return []
    if column == ALL_COLUMNS:
        if ALL_COLUMNS in scope_columns:
            return [ALL_COLUMNS]
        return sorted(scope_columns)
    if ALL_COLUMNS in scope_columns or column in scope_columns:
        return [column]
    return []


async def _load_role(
    repo: ClientSettingRepository, client_uid: UUID
) -> tuple[EffectiveRoleSummary | None, int | None]:
    """取 Client 的 Role 與其設定檔 pid;無指派 / Role 已刪 → 該側無任何授權。"""
    assignment = await repo.get_client_role(client_uid)
    if assignment is None:
        return None, None
    role = await repo.get_role_by_pid(assignment.role_pid)
    if role is None:
        return None, None
    profile = await repo.get_permission_profile_by_pid(role.permission_profile_pid)
    summary = EffectiveRoleSummary(
        uid=role.uid,
        name=role.name,
        permission_profile_uid=profile.uid if profile is not None else None,
        permission_profile_name=profile.name if profile is not None else None,
    )
    return summary, profile.pid if profile is not None else None


async def _load_exception_sets(
    repo: ClientSettingRepository, client_uid: UUID
) -> tuple[list[EffectiveExceptionSetSummary], list[int]]:
    """取未過期綁定對應的特例組(已軟刪的組不會回來,自然排除)。"""
    bindings = await repo.list_active_client_exception_sets(client_uid)
    if not bindings:
        return [], []
    expires_by_set = {row.exception_set_pid: row.expires_at for row in bindings}
    exception_sets = await repo.list_exception_sets_by_pids(list(expires_by_set))
    summaries = [
        EffectiveExceptionSetSummary(
            uid=row.uid, name=row.name, expires_at=expires_by_set[row.pid]
        )
        for row in exception_sets
    ]
    return summaries, [row.pid for row in exception_sets]


async def _collect_sources(
    repo: ClientSettingRepository, profile_pid: int | None, set_pids: list[int]
) -> list[_GrantSource]:
    sources: list[_GrantSource] = []
    if profile_pid is not None:
        opened = {
            row.operation_pid for row in await repo.list_profile_operations(profile_pid)
        }
        rows: list[_GrantRow] = [
            (item.operation_pid, item.table_name, item.column_name, item.action)
            for item in await repo.list_profile_items(profile_pid)
        ]
        sources.append((opened, rows))
    if set_pids:
        opened_by_set: dict[int, set[int]] = defaultdict(set)
        rows_by_set: dict[int, list[_GrantRow]] = defaultdict(list)
        for granted in await repo.list_exception_operations_by_set_pids(set_pids):
            opened_by_set[granted.exception_set_pid].add(granted.operation_pid)
        for item in await repo.list_exception_items_by_set_pids(set_pids):
            rows_by_set[item.exception_set_pid].append(
                (item.operation_pid, item.table_name, item.column_name, item.action)
            )
        sources.extend(
            (opened_by_set[set_pid], rows_by_set[set_pid]) for set_pid in set_pids
        )
    return sources


async def _load_scope(
    repo: ClientSettingRepository, operation_pids: list[int]
) -> dict[int, dict[str, set[str]]]:
    """作業範圍:`{作業 pid: {表: {欄位}}}`(一次載入全部作業,避免逐作業 N+1)。"""
    scope: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for item in await repo.list_operation_items_by_operation_pids(operation_pids):
        scope[item.operation_pid][item.table_name].add(item.column_name)
    return scope


async def _build_operations(
    repo: ClientSettingRepository, opened_pids: list[int], sources: list[_GrantSource]
) -> list[EffectiveOperationPermission]:
    scope = await _load_scope(repo, opened_pids)
    granted: dict[int, dict[str, dict[str, str]]] = {pid: {} for pid in opened_pids}
    for opened, rows in sources:
        for operation_pid, table_name, column_name, action in rows:
            if operation_pid not in opened:
                continue
            columns = _effective_columns(
                scope.get(operation_pid, {}).get(table_name, set()), column_name
            )
            if not columns:
                continue
            table = granted[operation_pid].setdefault(table_name, {})
            for column in columns:
                table[column] = _higher_action(table.get(column), action)

    services = {service.pid: service for service in await repo.list_services()}
    operations = [
        EffectiveOperationPermission(
            operation_uid=operation.uid,
            operation_name=operation.name,
            service_code=(
                services[operation.service_pid].code
                if operation.service_pid in services
                else ""
            ),
            tables={
                table_name: dict(sorted(_collapse_all_columns(columns).items()))
                for table_name, columns in sorted(granted[operation.pid].items())
            },
        )
        # 已軟刪的作業不會回來 → 其授權自動不出現在預覽
        for operation in await repo.list_operations_by_pids(opened_pids)
    ]
    operations.sort(key=lambda row: (row.service_code, row.operation_name))
    return operations


async def expand_effective_permissions(client_uid: UUID) -> EffectivePermissionsResponse:
    """直讀 RDS 展開最終可見欄位(不經快取;供快取回源與後續模組③ 沿用)。"""
    async with client_setting_session() as db:
        repo = ClientSettingRepository(db)
        role, profile_pid = await _load_role(repo, client_uid)
        exception_sets, set_pids = await _load_exception_sets(repo, client_uid)
        sources = await _collect_sources(repo, profile_pid, set_pids)
        opened_pids = sorted({pid for opened, _ in sources for pid in opened})
        operations = (
            await _build_operations(repo, opened_pids, sources) if opened_pids else []
        )
        return EffectivePermissionsResponse(
            client_uid=client_uid,
            role=role,
            exception_sets=exception_sets,
            operations=operations,
        )


class EffectivePermissionService:
    """單一 API Client 的最終可見欄位預覽(admin 後台;讀取走 Redis 快取)。"""

    def __init__(self, db: AsyncSession) -> None:
        # 自有 DB session:僅用於 API Client 存在性檢查(權限資料真身一律在 RDS)
        self._db = db

    async def preview(self, client_uid: UUID) -> EffectivePermissionsResponse:
        await self._ensure_client_exists(client_uid)
        return await permission_cache.get_or_load_model(
            permission_cache.effective_key(client_uid),
            EffectivePermissionsResponse,
            lambda: expand_effective_permissions(client_uid),
            ttl_seconds=permission_cache.DEFAULT_TTL_SECONDS,
        )

    async def _ensure_client_exists(self, client_uid: UUID) -> None:
        """不存在 / 已軟刪一律 404(api_client_repo 無「依 uid 取件」,沿用
        `api_client_service` 同款查詢下沉的前例)。"""
        found = (
            await self._db.execute(
                select(ApiClientUser.pid).where(
                    ApiClientUser.uid == client_uid,
                    ApiClientUser.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if found is None:
            raise AppError(_CLIENT_NOT_FOUND_DETAIL, response_code=404, status_code=404)
