import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'
import type { AuthProvider, UserRole } from '@/lib/api/authApi'

/** 角色下拉選項(供指派 UI 使用) */
export interface RoleOption {
  uid: string
  code: string
  name: string
  description: string | null
  is_builtin: boolean
}

export interface UserListItem {
  uid: string
  username: string
  /** 顯示名稱(SSO 姓名);無則前端 fallback 帳號 */
  display_name: string | null
  provider: AuthProvider
  role: UserRole
}

export interface UserListData {
  items: UserListItem[]
  total: number
  page: number
  page_size: number
}

export interface UserListParams {
  page: number
  pageSize: number
}

export interface AssignUserRolePayload {
  uid: string
  role: string
}

export const userApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['Role', 'User'] })
  .injectEndpoints({
    endpoints: (build) => ({
      listRoles: build.query<RoleOption[], void>({
        query: () => '/roles',
        providesTags: [{ type: 'Role', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<{ items: RoleOption[] }>,
        ): RoleOption[] => unwrap(response).items,
      }),
      listUsers: build.query<UserListData, UserListParams>({
        query: ({ page, pageSize }) => ({
          url: '/users',
          params: { page, page_size: pageSize },
        }),
        providesTags: [{ type: 'User', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<UserListData>): UserListData =>
          unwrap(response),
      }),
      assignUserRole: build.mutation<UserListItem, AssignUserRolePayload>({
        query: ({ uid, role }) => ({
          url: `/users/${uid}/role`,
          method: 'PATCH',
          body: { role },
        }),
        invalidatesTags: [{ type: 'User', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<UserListItem>): UserListItem =>
          unwrap(response),
      }),
    }),
  })

export const { useListRolesQuery, useListUsersQuery, useAssignUserRoleMutation } =
  userApi
