'use client'

import { memo, useCallback, useMemo, useState } from 'react'
import {
  useAssignUserRoleMutation,
  useListRolesQuery,
  useListUsersQuery,
  type UserListItem,
} from '@/lib/api/userApi'
import { useAuth } from '@/lib/auth/useAuth'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Pagination } from '@/components/common/Pagination'
import { extractApiErrorDetail } from '@/utils/apiError'

const PAGE_SIZE = 20

const PROVIDER_LABELS: Record<string, string> = {
  sso: 'SSO',
  local: '本地',
}

const PROVIDER_CLASSES: Record<string, string> = {
  sso: 'bg-info/15 text-info',
  local: 'bg-muted text-muted-foreground',
}

interface ProviderBadgeProps {
  provider: string
}

const ProviderBadge = memo(function ProviderBadge({
  provider,
}: ProviderBadgeProps): React.ReactNode {
  const label = PROVIDER_LABELS[provider] ?? provider
  const badgeClass = PROVIDER_CLASSES[provider] ?? 'bg-muted text-muted-foreground'
  return <span className={`df-badge ${badgeClass}`}>{label}</span>
})

interface RoleOptionItem {
  code: string
  name: string
}

interface UserRowProps {
  user: UserListItem
  isSelf: boolean
  roleName: string
  roleOptions: RoleOptionItem[]
  onRequestAssign: (user: UserListItem, toRoleCode: string) => void
}

const UserRow = memo(function UserRow({
  user,
  isSelf,
  roleName,
  roleOptions,
  onRequestAssign,
}: UserRowProps): React.ReactNode {
  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      onRequestAssign(user, event.target.value)
    },
    [onRequestAssign, user],
  )

  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3 text-sm font-medium text-foreground md:text-base">
        {user.username}
      </td>
      <td className="df-td text-muted-foreground">
        {user.display_name ?? user.username}
      </td>
      <td className="px-3 py-3">
        <ProviderBadge provider={user.provider} />
      </td>
      <td className="px-3 py-3">
        {isSelf ? (
          <div className="flex flex-col gap-1">
            <select
              value={user.role}
              disabled
              title="無法變更自己的角色"
              className="df-input w-auto min-w-[8rem] opacity-60"
            >
              <option value={user.role}>{roleName}</option>
            </select>
            <p className="text-sm text-muted-foreground md:text-base">
              無法變更自己的角色
            </p>
          </div>
        ) : (
          <select
            value={user.role}
            onChange={handleChange}
            className="df-input w-auto min-w-[8rem]"
          >
            {roleOptions.map((role) => (
              <option key={role.code} value={role.code}>
                {role.name}
              </option>
            ))}
          </select>
        )}
      </td>
    </tr>
  )
})

interface PendingAssign {
  uid: string
  username: string
  fromRoleName: string
  toRoleCode: string
  toRoleName: string
}

/** 使用者與角色清單(admin only):帳號 / 顯示名稱 / 登入來源 / 角色指派 */
export function UserRoleTable(): React.ReactNode {
  const { user: currentUser } = useAuth()
  const [page, setPage] = useState(1)
  const [pending, setPending] = useState<PendingAssign | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const {
    data: roles,
    isLoading: rolesLoading,
    isError: rolesError,
  } = useListRolesQuery()
  const { data, isLoading, isError, isFetching } = useListUsersQuery({
    page,
    pageSize: PAGE_SIZE,
  })
  const [assignRole, { isLoading: isAssigning }] = useAssignUserRoleMutation()

  const roleNameMap = useMemo((): Record<string, string> => {
    const map: Record<string, string> = {}
    for (const role of roles ?? []) {
      map[role.code] = role.name
    }
    return map
  }, [roles])

  const roleOptions = useMemo(
    (): RoleOptionItem[] =>
      (roles ?? []).map((role) => ({ code: role.code, name: role.name })),
    [roles],
  )

  const handlePageChange = useCallback((next: number): void => {
    setPage(next)
  }, [])

  const handleRequestAssign = useCallback(
    (target: UserListItem, toRoleCode: string): void => {
      if (toRoleCode === target.role) return
      setActionError(null)
      setPending({
        uid: target.uid,
        username: target.username,
        fromRoleName: roleNameMap[target.role] ?? target.role,
        toRoleCode,
        toRoleName: roleNameMap[toRoleCode] ?? toRoleCode,
      })
    },
    [roleNameMap],
  )

  const closePending = useCallback((): void => {
    setPending(null)
  }, [])

  const handleConfirmAssign = useCallback(async (): Promise<void> => {
    if (pending === null) return
    setActionError(null)
    const result = await assignRole({ uid: pending.uid, role: pending.toRoleCode })
    setPending(null)
    if ('error' in result) {
      setActionError(
        extractApiErrorDetail(result.error, '指派角色失敗,請稍後再試'),
      )
    }
  }, [pending, assignRole])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-foreground md:text-2xl">
          使用者與角色
        </h1>
        <p className="mt-1 text-sm text-muted-foreground md:text-base">
          管理系統使用者的角色指派(admin 專用)
        </p>
      </div>

      {actionError !== null ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {actionError}
        </p>
      ) : null}

      {rolesError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入角色清單失敗,請稍後再試
        </p>
      ) : null}

      {isLoading || rolesLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入使用者清單失敗,請稍後再試
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div
            className={`df-card overflow-x-auto transition-opacity ${isFetching ? 'opacity-60' : ''}`}
          >
            <table className="df-table min-w-[720px]">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="df-th">帳號</th>
                  <th className="df-th">顯示名稱</th>
                  <th className="df-th">登入來源</th>
                  <th className="df-th">角色</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <UserRow
                    key={item.uid}
                    user={item}
                    isSelf={item.uid === currentUser?.uid}
                    roleName={roleNameMap[item.role] ?? item.role}
                    roleOptions={roleOptions}
                    onRequestAssign={handleRequestAssign}
                  />
                ))}
              </tbody>
            </table>
            {data.items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
                尚無使用者
              </p>
            ) : null}
          </div>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={handlePageChange}
          />
        </>
      ) : null}

      <ConfirmDialog
        open={pending !== null}
        title="變更使用者角色"
        confirmLabel="確認變更"
        confirmDisabled={isAssigning}
        onConfirm={handleConfirmAssign}
        onCancel={closePending}
      >
        {pending !== null ? (
          <p className="text-foreground">
            將「{pending.username}」的角色由 <strong>{pending.fromRoleName}</strong>{' '}
            變更為 <strong>{pending.toRoleName}</strong>。
          </p>
        ) : null}
        <p>變更立即生效,請確認無誤後再送出。</p>
      </ConfirmDialog>
    </section>
  )
}
