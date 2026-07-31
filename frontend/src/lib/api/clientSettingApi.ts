import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/**
 * 組織權限管理 API 層(v1.6.1 task-008)。
 *
 * 對應後端 `/api/v1/client-settings` 前綴(admin-only,見 `backend/app/api/v1/client_settings.py`):
 * 系統別 → 作業(表 × 欄位範圍)→ 權限設定檔(勾作業 + 授權矩陣)→ Role(綁 1 設定檔);
 * 特例權限組(task-006)結構與設定檔對稱,獨立可重用、可綁多個 API Client。
 *
 * **不含**:API Client 的 Role 指派 / 特例綁定 / 最終權限預覽(`effective-permissions`)
 * ——這三者依 task-010 規格併入既有 `apiClientApi.ts`(該頁「權限」面板專用,勿在此重複實作)。
 *
 * list 類回應統一 `{items, total}`(無分頁);寫入端點 invalidatesTags 對應清單標籤,
 * 讓 RTK Query cache 於任一寫入後自動 refetch。
 */

/** 授權矩陣動作:read(唯讀)/ edit(含新增 / 更新 / 軟刪) */
export type PermissionAction = 'read' | 'edit'

/** 表 × 欄位範圍項(語意層英文名;`column_name = '*'` = 該表全欄位) */
export interface ScopeItem {
  table_name: string
  column_name: string
}

/** 授權矩陣項:範圍項 + 動作 */
export interface PermissionItem extends ScopeItem {
  action: PermissionAction
}

/** 後端 list 類回應統一形狀(無分頁) */
export interface ListData<T> {
  items: T[]
  total: number
}

/* ---------------------------------------------------------------------- */
/* 系統別 services                                                          */
/* ---------------------------------------------------------------------- */

export interface ClientSettingService {
  uid: string
  code: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export type ClientSettingServiceListData = ListData<ClientSettingService>

export interface CreateClientSettingServicePayload {
  code: string
  name: string
  description: string | null
}

export interface UpdateClientSettingServicePayload {
  uid: string
  name?: string
  description?: string | null
}

/* ---------------------------------------------------------------------- */
/* 作業 operations                                                          */
/* ---------------------------------------------------------------------- */

export interface ClientSettingOperation {
  uid: string
  service_uid: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export type ClientSettingOperationListData = ListData<ClientSettingOperation>

export interface CreateClientSettingOperationPayload {
  service_uid: string
  name: string
  description: string | null
}

export interface UpdateClientSettingOperationPayload {
  uid: string
  name?: string
  description?: string | null
}

/* ---------------------------------------------------------------------- */
/* 作業範圍 operation_items(表 × 欄位)                                      */
/* ---------------------------------------------------------------------- */

export interface OperationItem {
  uid: string
  table_name: string
  column_name: string
}

export type OperationItemListData = ListData<OperationItem>

export interface ReplaceOperationItemsPayload {
  uid: string
  items: ScopeItem[]
}

/* ---------------------------------------------------------------------- */
/* 權限設定檔 permission_profiles                                           */
/* ---------------------------------------------------------------------- */

export interface PermissionProfile {
  uid: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export type PermissionProfileListData = ListData<PermissionProfile>

export interface CreatePermissionProfilePayload {
  name: string
  description: string | null
}

export interface UpdatePermissionProfilePayload {
  uid: string
  name?: string
  description?: string | null
}

/* ---------------------------------------------------------------------- */
/* 設定檔勾選作業 profile_operations                                        */
/* ---------------------------------------------------------------------- */

export interface ProfileOperation {
  uid: string
  operation_uid: string
}

export type ProfileOperationListData = ListData<ProfileOperation>

export interface ReplaceProfileOperationsPayload {
  uid: string
  operation_uids: string[]
}

/* ---------------------------------------------------------------------- */
/* 設定檔授權矩陣 profile_items(作業 × 表 × 欄位 × read/edit)               */
/* ---------------------------------------------------------------------- */

export interface ProfileItem {
  uid: string
  table_name: string
  column_name: string
  action: PermissionAction
}

export type ProfileItemListData = ListData<ProfileItem>

export interface ListProfileItemsParams {
  uid: string
  operationUid: string
}

export interface ReplaceProfileItemsPayload {
  uid: string
  operationUid: string
  items: PermissionItem[]
}

/* ---------------------------------------------------------------------- */
/* Role(API Client 角色;與後台人員角色 /api/v1/roles 不同資源)             */
/* ---------------------------------------------------------------------- */

export interface ClientSettingRole {
  uid: string
  permission_profile_uid: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export type ClientSettingRoleListData = ListData<ClientSettingRole>

export interface CreateClientSettingRolePayload {
  permission_profile_uid: string
  name: string
  description: string | null
}

export interface UpdateClientSettingRolePayload {
  uid: string
  permission_profile_uid?: string
  name?: string
  description?: string | null
}

/* ---------------------------------------------------------------------- */
/* 特例權限組 exception_sets(結構同設定檔,可重用 / 可綁多個 Client)         */
/* ---------------------------------------------------------------------- */

export interface ExceptionSet {
  uid: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export type ExceptionSetListData = ListData<ExceptionSet>

export interface CreateExceptionSetPayload {
  name: string
  description: string | null
}

export interface UpdateExceptionSetPayload {
  uid: string
  name?: string
  description?: string | null
}

export interface ExceptionOperation {
  uid: string
  operation_uid: string
}

export type ExceptionOperationListData = ListData<ExceptionOperation>

export interface ReplaceExceptionOperationsPayload {
  uid: string
  operation_uids: string[]
}

export interface ExceptionItem {
  uid: string
  table_name: string
  column_name: string
  action: PermissionAction
}

export type ExceptionItemListData = ListData<ExceptionItem>

export interface ListExceptionItemsParams {
  uid: string
  operationUid: string
}

export interface ReplaceExceptionItemsPayload {
  uid: string
  operationUid: string
  items: PermissionItem[]
}

/* ---------------------------------------------------------------------- */
/* endpoints                                                                */
/* ---------------------------------------------------------------------- */

export const clientSettingApi = baseApi
  .enhanceEndpoints({
    addTagTypes: [
      'ClientSettingService',
      'ClientSettingOperation',
      'ClientSettingOperationItems',
      'ClientSettingProfile',
      'ClientSettingProfileOperations',
      'ClientSettingProfileItems',
      'ClientSettingRole',
      'ClientSettingExceptionSet',
      'ClientSettingExceptionOperations',
      'ClientSettingExceptionItems',
    ],
  })
  .injectEndpoints({
    endpoints: (build) => ({
      // ── 系統別 ──────────────────────────────────────────────────────
      listServices: build.query<ClientSettingServiceListData, void>({
        query: () => ({ url: '/client-settings/services' }),
        providesTags: [{ type: 'ClientSettingService', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingServiceListData>,
        ): ClientSettingServiceListData => unwrap(response),
      }),
      createService: build.mutation<ClientSettingService, CreateClientSettingServicePayload>({
        query: (body) => ({ url: '/client-settings/services', method: 'POST', body }),
        invalidatesTags: [{ type: 'ClientSettingService', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingService>,
        ): ClientSettingService => unwrap(response),
      }),
      updateService: build.mutation<ClientSettingService, UpdateClientSettingServicePayload>({
        query: ({ uid, ...body }) => ({
          url: `/client-settings/services/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [{ type: 'ClientSettingService', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingService>,
        ): ClientSettingService => unwrap(response),
      }),
      deleteService: build.mutation<ClientSettingService, string>({
        query: (uid) => ({ url: `/client-settings/services/${uid}`, method: 'DELETE' }),
        invalidatesTags: [
          { type: 'ClientSettingService', id: 'LIST' },
          { type: 'ClientSettingOperation', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<ClientSettingService>,
        ): ClientSettingService => unwrap(response),
      }),

      // ── 作業 ────────────────────────────────────────────────────────
      listOperations: build.query<ClientSettingOperationListData, string | void>({
        query: (serviceUid) => ({
          url: '/client-settings/operations',
          params: serviceUid ? { service_uid: serviceUid } : undefined,
        }),
        providesTags: [{ type: 'ClientSettingOperation', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingOperationListData>,
        ): ClientSettingOperationListData => unwrap(response),
      }),
      createOperation: build.mutation<
        ClientSettingOperation,
        CreateClientSettingOperationPayload
      >({
        query: (body) => ({ url: '/client-settings/operations', method: 'POST', body }),
        invalidatesTags: [{ type: 'ClientSettingOperation', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingOperation>,
        ): ClientSettingOperation => unwrap(response),
      }),
      updateOperation: build.mutation<
        ClientSettingOperation,
        UpdateClientSettingOperationPayload
      >({
        query: ({ uid, ...body }) => ({
          url: `/client-settings/operations/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [{ type: 'ClientSettingOperation', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingOperation>,
        ): ClientSettingOperation => unwrap(response),
      }),
      deleteOperation: build.mutation<ClientSettingOperation, string>({
        query: (uid) => ({ url: `/client-settings/operations/${uid}`, method: 'DELETE' }),
        invalidatesTags: [
          { type: 'ClientSettingOperation', id: 'LIST' },
          { type: 'ClientSettingOperationItems', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<ClientSettingOperation>,
        ): ClientSettingOperation => unwrap(response),
      }),

      // ── 作業範圍(表 × 欄位)────────────────────────────────────────
      listOperationItems: build.query<OperationItemListData, string>({
        query: (uid) => ({ url: `/client-settings/operations/${uid}/items` }),
        providesTags: (_result, _error, uid) => [
          { type: 'ClientSettingOperationItems', id: uid },
        ],
        transformResponse: (
          response: ApiEnvelope<OperationItemListData>,
        ): OperationItemListData => unwrap(response),
      }),
      replaceOperationItems: build.mutation<OperationItemListData, ReplaceOperationItemsPayload>({
        query: ({ uid, items }) => ({
          url: `/client-settings/operations/${uid}/items`,
          method: 'PUT',
          body: { items },
        }),
        invalidatesTags: (_result, _error, { uid }) => [
          { type: 'ClientSettingOperationItems', id: uid },
          { type: 'ClientSettingOperationItems', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<OperationItemListData>,
        ): OperationItemListData => unwrap(response),
      }),

      // ── 權限設定檔 ──────────────────────────────────────────────────
      listPermissionProfiles: build.query<PermissionProfileListData, void>({
        query: () => ({ url: '/client-settings/profiles' }),
        providesTags: [{ type: 'ClientSettingProfile', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<PermissionProfileListData>,
        ): PermissionProfileListData => unwrap(response),
      }),
      createPermissionProfile: build.mutation<
        PermissionProfile,
        CreatePermissionProfilePayload
      >({
        query: (body) => ({ url: '/client-settings/profiles', method: 'POST', body }),
        invalidatesTags: [{ type: 'ClientSettingProfile', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<PermissionProfile>,
        ): PermissionProfile => unwrap(response),
      }),
      updatePermissionProfile: build.mutation<
        PermissionProfile,
        UpdatePermissionProfilePayload
      >({
        query: ({ uid, ...body }) => ({
          url: `/client-settings/profiles/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [{ type: 'ClientSettingProfile', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<PermissionProfile>,
        ): PermissionProfile => unwrap(response),
      }),
      deletePermissionProfile: build.mutation<PermissionProfile, string>({
        query: (uid) => ({ url: `/client-settings/profiles/${uid}`, method: 'DELETE' }),
        invalidatesTags: [
          { type: 'ClientSettingProfile', id: 'LIST' },
          { type: 'ClientSettingRole', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<PermissionProfile>,
        ): PermissionProfile => unwrap(response),
      }),

      // ── 設定檔勾選作業 ──────────────────────────────────────────────
      listProfileOperations: build.query<ProfileOperationListData, string>({
        query: (uid) => ({ url: `/client-settings/profiles/${uid}/operations` }),
        providesTags: (_result, _error, uid) => [
          { type: 'ClientSettingProfileOperations', id: uid },
        ],
        transformResponse: (
          response: ApiEnvelope<ProfileOperationListData>,
        ): ProfileOperationListData => unwrap(response),
      }),
      replaceProfileOperations: build.mutation<
        ProfileOperationListData,
        ReplaceProfileOperationsPayload
      >({
        query: ({ uid, operation_uids }) => ({
          url: `/client-settings/profiles/${uid}/operations`,
          method: 'PUT',
          body: { operation_uids },
        }),
        invalidatesTags: (_result, _error, { uid }) => [
          { type: 'ClientSettingProfileOperations', id: uid },
          { type: 'ClientSettingProfileItems', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<ProfileOperationListData>,
        ): ProfileOperationListData => unwrap(response),
      }),

      // ── 設定檔授權矩陣 ──────────────────────────────────────────────
      listProfileItems: build.query<ProfileItemListData, ListProfileItemsParams>({
        query: ({ uid, operationUid }) => ({
          url: `/client-settings/profiles/${uid}/operations/${operationUid}/items`,
        }),
        providesTags: (_result, _error, { uid, operationUid }) => [
          { type: 'ClientSettingProfileItems', id: `${uid}-${operationUid}` },
        ],
        transformResponse: (
          response: ApiEnvelope<ProfileItemListData>,
        ): ProfileItemListData => unwrap(response),
      }),
      replaceProfileItems: build.mutation<ProfileItemListData, ReplaceProfileItemsPayload>({
        query: ({ uid, operationUid, items }) => ({
          url: `/client-settings/profiles/${uid}/operations/${operationUid}/items`,
          method: 'PUT',
          body: { items },
        }),
        invalidatesTags: (_result, _error, { uid, operationUid }) => [
          { type: 'ClientSettingProfileItems', id: `${uid}-${operationUid}` },
        ],
        transformResponse: (
          response: ApiEnvelope<ProfileItemListData>,
        ): ProfileItemListData => unwrap(response),
      }),

      // ── Role ────────────────────────────────────────────────────────
      listClientSettingRoles: build.query<ClientSettingRoleListData, void>({
        query: () => ({ url: '/client-settings/roles' }),
        providesTags: [{ type: 'ClientSettingRole', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingRoleListData>,
        ): ClientSettingRoleListData => unwrap(response),
      }),
      createClientSettingRole: build.mutation<
        ClientSettingRole,
        CreateClientSettingRolePayload
      >({
        query: (body) => ({ url: '/client-settings/roles', method: 'POST', body }),
        invalidatesTags: [{ type: 'ClientSettingRole', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingRole>,
        ): ClientSettingRole => unwrap(response),
      }),
      updateClientSettingRole: build.mutation<
        ClientSettingRole,
        UpdateClientSettingRolePayload
      >({
        query: ({ uid, ...body }) => ({
          url: `/client-settings/roles/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [{ type: 'ClientSettingRole', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingRole>,
        ): ClientSettingRole => unwrap(response),
      }),
      deleteClientSettingRole: build.mutation<ClientSettingRole, string>({
        query: (uid) => ({ url: `/client-settings/roles/${uid}`, method: 'DELETE' }),
        invalidatesTags: [{ type: 'ClientSettingRole', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ClientSettingRole>,
        ): ClientSettingRole => unwrap(response),
      }),

      // ── 特例權限組 ──────────────────────────────────────────────────
      listExceptionSets: build.query<ExceptionSetListData, void>({
        query: () => ({ url: '/client-settings/exception-sets' }),
        providesTags: [{ type: 'ClientSettingExceptionSet', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ExceptionSetListData>,
        ): ExceptionSetListData => unwrap(response),
      }),
      createExceptionSet: build.mutation<ExceptionSet, CreateExceptionSetPayload>({
        query: (body) => ({ url: '/client-settings/exception-sets', method: 'POST', body }),
        invalidatesTags: [{ type: 'ClientSettingExceptionSet', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<ExceptionSet>): ExceptionSet =>
          unwrap(response),
      }),
      updateExceptionSet: build.mutation<ExceptionSet, UpdateExceptionSetPayload>({
        query: ({ uid, ...body }) => ({
          url: `/client-settings/exception-sets/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [{ type: 'ClientSettingExceptionSet', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<ExceptionSet>): ExceptionSet =>
          unwrap(response),
      }),
      deleteExceptionSet: build.mutation<ExceptionSet, string>({
        query: (uid) => ({ url: `/client-settings/exception-sets/${uid}`, method: 'DELETE' }),
        invalidatesTags: [{ type: 'ClientSettingExceptionSet', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<ExceptionSet>): ExceptionSet =>
          unwrap(response),
      }),

      // ── 特例組勾選作業 ──────────────────────────────────────────────
      listExceptionOperations: build.query<ExceptionOperationListData, string>({
        query: (uid) => ({ url: `/client-settings/exception-sets/${uid}/operations` }),
        providesTags: (_result, _error, uid) => [
          { type: 'ClientSettingExceptionOperations', id: uid },
        ],
        transformResponse: (
          response: ApiEnvelope<ExceptionOperationListData>,
        ): ExceptionOperationListData => unwrap(response),
      }),
      replaceExceptionOperations: build.mutation<
        ExceptionOperationListData,
        ReplaceExceptionOperationsPayload
      >({
        query: ({ uid, operation_uids }) => ({
          url: `/client-settings/exception-sets/${uid}/operations`,
          method: 'PUT',
          body: { operation_uids },
        }),
        invalidatesTags: (_result, _error, { uid }) => [
          { type: 'ClientSettingExceptionOperations', id: uid },
          { type: 'ClientSettingExceptionItems', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<ExceptionOperationListData>,
        ): ExceptionOperationListData => unwrap(response),
      }),

      // ── 特例組授權矩陣 ──────────────────────────────────────────────
      listExceptionItems: build.query<ExceptionItemListData, ListExceptionItemsParams>({
        query: ({ uid, operationUid }) => ({
          url: `/client-settings/exception-sets/${uid}/operations/${operationUid}/items`,
        }),
        providesTags: (_result, _error, { uid, operationUid }) => [
          { type: 'ClientSettingExceptionItems', id: `${uid}-${operationUid}` },
        ],
        transformResponse: (
          response: ApiEnvelope<ExceptionItemListData>,
        ): ExceptionItemListData => unwrap(response),
      }),
      replaceExceptionItems: build.mutation<ExceptionItemListData, ReplaceExceptionItemsPayload>({
        query: ({ uid, operationUid, items }) => ({
          url: `/client-settings/exception-sets/${uid}/operations/${operationUid}/items`,
          method: 'PUT',
          body: { items },
        }),
        invalidatesTags: (_result, _error, { uid, operationUid }) => [
          { type: 'ClientSettingExceptionItems', id: `${uid}-${operationUid}` },
        ],
        transformResponse: (
          response: ApiEnvelope<ExceptionItemListData>,
        ): ExceptionItemListData => unwrap(response),
      }),
    }),
  })

export const {
  useListServicesQuery,
  useCreateServiceMutation,
  useUpdateServiceMutation,
  useDeleteServiceMutation,
  useListOperationsQuery,
  useCreateOperationMutation,
  useUpdateOperationMutation,
  useDeleteOperationMutation,
  useListOperationItemsQuery,
  useReplaceOperationItemsMutation,
  useListPermissionProfilesQuery,
  useCreatePermissionProfileMutation,
  useUpdatePermissionProfileMutation,
  useDeletePermissionProfileMutation,
  useListProfileOperationsQuery,
  useReplaceProfileOperationsMutation,
  useListProfileItemsQuery,
  useReplaceProfileItemsMutation,
  useListClientSettingRolesQuery,
  useCreateClientSettingRoleMutation,
  useUpdateClientSettingRoleMutation,
  useDeleteClientSettingRoleMutation,
  useListExceptionSetsQuery,
  useCreateExceptionSetMutation,
  useUpdateExceptionSetMutation,
  useDeleteExceptionSetMutation,
  useListExceptionOperationsQuery,
  useReplaceExceptionOperationsMutation,
  useListExceptionItemsQuery,
  useReplaceExceptionItemsMutation,
} = clientSettingApi
