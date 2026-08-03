import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** API Client 狀態(enabled 可正常取 token;disabled 立即拒發) */
export type ApiClientStatus = 'enabled' | 'disabled'

export interface ApiClientListItem {
  uid: string
  client_id: string
  name: string
  description: string | null
  status: ApiClientStatus
  rate_limit_per_minute: number
  rate_limit_per_10min: number
  active_secret_count: number
  created_at: string
}

export interface ApiClientListData {
  items: ApiClientListItem[]
  total: number
  page: number
  page_size: number
}

export interface ApiClientListParams {
  page: number
  pageSize: number
}

export interface CreateApiClientPayload {
  name: string
  description: string | null
}

export interface CreateApiClientResult {
  client: ApiClientListItem
  secret_uid: string
  client_secret: string
}

/** 密鑰狀態(active 可用於取 token;retired 立即失效但保留紀錄) */
export type ApiClientSecretStatus = 'active' | 'retired'

export interface ApiClientSecretItem {
  uid: string
  status: ApiClientSecretStatus
  created_at: string
  /** false = task-009 前核發的舊密鑰,無可檢視明文(須輪替後才可檢視) */
  revealable: boolean
}

export interface ApiClientSecretListData {
  items: ApiClientSecretItem[]
  total: number
}

export interface UpdateApiClientPayload {
  uid: string
  name?: string
  description?: string | null
  status?: ApiClientStatus
  rate_limit_per_minute?: number
  rate_limit_per_10min?: number
}

export interface RotateApiClientSecretResult {
  secret_uid: string
  client_secret: string
  active_secret_count: number
}

export interface RetireApiClientSecretPayload {
  uid: string
  secretUid: string
}

export interface RevealApiClientSecretPayload {
  uid: string
  secretUid: string
}

export interface RevealApiClientSecretResult {
  secret_uid: string
  client_secret: string
}

/* ---------------------------------------------------------------------- */
/* 權限指派 / 檢視(v1.6.1 task-010;端點屬 /client-settings、/api-clients 前綴, */
/* 型別集中放此檔,對應 clientSettingApi.ts 頂部註記)                          */
/* ---------------------------------------------------------------------- */

/** Client 的角色指派(0..1);與 `ClientSettingRole`(角色定義本身)不同資源 */
export interface ClientRoleAssignment {
  uid: string
  api_client_uid: string
  role_uid: string
  created_at: string
  updated_at: string
}

export interface AssignClientRolePayload {
  clientUid: string
  role_uid: string
}

/** Client 的臨時權限組綁定列(0..N,各自效期) */
export interface ClientExceptionSetBinding {
  uid: string
  api_client_uid: string
  exception_set_uid: string
  exception_set_name: string
  expires_at: string | null
  is_expired: boolean
}

export interface ClientExceptionSetBindingListData {
  items: ClientExceptionSetBinding[]
  total: number
}

export interface BindClientExceptionSetPayload {
  clientUid: string
  exception_set_uid: string
  /** 台北 wall-clock `YYYY-MM-DDTHH:mm:ss`;省略 / null = 不設限 */
  expires_at?: string | null
}

export interface UnbindClientExceptionSetPayload {
  clientUid: string
  bindingUid: string
}

/** 授權動作:read(唯讀)/ edit(含新增 / 更新 / 軟刪) */
export type EffectivePermissionAction = 'read' | 'edit'

export interface EffectiveRoleSummary {
  uid: string
  name: string
  permission_profile_uid: string | null
  permission_profile_name: string | null
}

export interface EffectiveExceptionSetSummary {
  uid: string
  name: string
  expires_at: string | null
}

export interface EffectiveOperationPermission {
  operation_uid: string
  operation_name: string
  service_code: string
  /** `{表: {欄位: read/edit}}`;空物件 = 作業有入口但無可見欄位(default-closed) */
  tables: Record<string, Record<string, EffectivePermissionAction>>
}

/** 單一 API Client 的最終權限預覽(角色綁定的角色權限設定檔 ∪ 未過期臨時權限,再 ∩ 作業範圍) */
export interface EffectivePermissions {
  client_uid: string
  role: EffectiveRoleSummary | null
  exception_sets: EffectiveExceptionSetSummary[]
  operations: EffectiveOperationPermission[]
}

export const apiClientApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['ApiClient', 'ApiClientPermission', 'ApiClientExceptionSet'] })
  .injectEndpoints({
    endpoints: (build) => ({
      listApiClients: build.query<ApiClientListData, ApiClientListParams>({
        query: ({ page, pageSize }) => ({
          url: '/api-clients',
          params: { page, page_size: pageSize },
        }),
        providesTags: [{ type: 'ApiClient', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ApiClientListData>,
        ): ApiClientListData => unwrap(response),
      }),
      listApiClientSecrets: build.query<ApiClientSecretListData, string>({
        query: (uid) => ({ url: `/api-clients/${uid}/secrets` }),
        providesTags: (_result, _error, uid) => [
          { type: 'ApiClient', id: `SECRETS-${uid}` },
        ],
        transformResponse: (
          response: ApiEnvelope<ApiClientSecretListData>,
        ): ApiClientSecretListData => unwrap(response),
      }),
      createApiClient: build.mutation<CreateApiClientResult, CreateApiClientPayload>({
        query: (body) => ({ url: '/api-clients', method: 'POST', body }),
        invalidatesTags: [{ type: 'ApiClient', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<CreateApiClientResult>,
        ): CreateApiClientResult => unwrap(response),
      }),
      updateApiClient: build.mutation<ApiClientListItem, UpdateApiClientPayload>({
        query: ({ uid, ...body }) => ({
          url: `/api-clients/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [{ type: 'ApiClient', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ApiClientListItem>,
        ): ApiClientListItem => unwrap(response),
      }),
      deleteApiClient: build.mutation<ApiClientListItem, string>({
        query: (uid) => ({ url: `/api-clients/${uid}`, method: 'DELETE' }),
        invalidatesTags: [{ type: 'ApiClient', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ApiClientListItem>,
        ): ApiClientListItem => unwrap(response),
      }),
      rotateApiClientSecret: build.mutation<RotateApiClientSecretResult, string>({
        query: (uid) => ({ url: `/api-clients/${uid}/rotate-secret`, method: 'POST' }),
        invalidatesTags: (_result, _error, uid) => [
          { type: 'ApiClient', id: 'LIST' },
          { type: 'ApiClient', id: `SECRETS-${uid}` },
        ],
        transformResponse: (
          response: ApiEnvelope<RotateApiClientSecretResult>,
        ): RotateApiClientSecretResult => unwrap(response),
      }),
      // 後端為 GET,此處刻意用 mutation:明文只回呼叫端元件 state,不進 RTK 查詢快取
      revealApiClientSecret: build.mutation<
        RevealApiClientSecretResult,
        RevealApiClientSecretPayload
      >({
        query: ({ uid, secretUid }) => ({
          url: `/api-clients/${uid}/secrets/${secretUid}/reveal`,
          method: 'GET',
        }),
        transformResponse: (
          response: ApiEnvelope<RevealApiClientSecretResult>,
        ): RevealApiClientSecretResult => unwrap(response),
      }),
      retireApiClientSecret: build.mutation<
        ApiClientListItem,
        RetireApiClientSecretPayload
      >({
        query: ({ uid, secretUid }) => ({
          url: `/api-clients/${uid}/secrets/${secretUid}/retire`,
          method: 'POST',
        }),
        invalidatesTags: (_result, _error, { uid }) => [
          { type: 'ApiClient', id: 'LIST' },
          { type: 'ApiClient', id: `SECRETS-${uid}` },
        ],
        transformResponse: (
          response: ApiEnvelope<ApiClientListItem>,
        ): ApiClientListItem => unwrap(response),
      }),

      // ── 權限指派 / 檢視(task-010)──────────────────────────────────
      getEffectivePermissions: build.query<EffectivePermissions, string>({
        query: (clientUid) => ({ url: `/api-clients/${clientUid}/effective-permissions` }),
        providesTags: (_result, _error, clientUid) => [
          { type: 'ApiClientPermission', id: clientUid },
        ],
        transformResponse: (
          response: ApiEnvelope<EffectivePermissions>,
        ): EffectivePermissions => unwrap(response),
      }),
      assignClientRole: build.mutation<ClientRoleAssignment, AssignClientRolePayload>({
        query: ({ clientUid, ...body }) => ({
          url: `/client-settings/clients/${clientUid}/role`,
          method: 'PUT',
          body,
        }),
        invalidatesTags: (_result, _error, { clientUid }) => [
          { type: 'ApiClientPermission', id: clientUid },
        ],
        transformResponse: (
          response: ApiEnvelope<ClientRoleAssignment>,
        ): ClientRoleAssignment => unwrap(response),
      }),
      removeClientRole: build.mutation<ClientRoleAssignment, string>({
        query: (clientUid) => ({
          url: `/client-settings/clients/${clientUid}/role`,
          method: 'DELETE',
        }),
        invalidatesTags: (_result, _error, clientUid) => [
          { type: 'ApiClientPermission', id: clientUid },
        ],
        transformResponse: (
          response: ApiEnvelope<ClientRoleAssignment>,
        ): ClientRoleAssignment => unwrap(response),
      }),
      listClientExceptionSets: build.query<ClientExceptionSetBindingListData, string>({
        query: (clientUid) => ({
          url: `/client-settings/clients/${clientUid}/exception-sets`,
        }),
        providesTags: (_result, _error, clientUid) => [
          { type: 'ApiClientExceptionSet', id: clientUid },
        ],
        transformResponse: (
          response: ApiEnvelope<ClientExceptionSetBindingListData>,
        ): ClientExceptionSetBindingListData => unwrap(response),
      }),
      bindClientExceptionSet: build.mutation<
        ClientExceptionSetBinding,
        BindClientExceptionSetPayload
      >({
        query: ({ clientUid, ...body }) => ({
          url: `/client-settings/clients/${clientUid}/exception-sets`,
          method: 'POST',
          body,
        }),
        invalidatesTags: (_result, _error, { clientUid }) => [
          { type: 'ApiClientPermission', id: clientUid },
          { type: 'ApiClientExceptionSet', id: clientUid },
        ],
        transformResponse: (
          response: ApiEnvelope<ClientExceptionSetBinding>,
        ): ClientExceptionSetBinding => unwrap(response),
      }),
      unbindClientExceptionSet: build.mutation<
        ClientExceptionSetBinding,
        UnbindClientExceptionSetPayload
      >({
        query: ({ clientUid, bindingUid }) => ({
          url: `/client-settings/clients/${clientUid}/exception-sets/${bindingUid}`,
          method: 'DELETE',
        }),
        invalidatesTags: (_result, _error, { clientUid }) => [
          { type: 'ApiClientPermission', id: clientUid },
          { type: 'ApiClientExceptionSet', id: clientUid },
        ],
        transformResponse: (
          response: ApiEnvelope<ClientExceptionSetBinding>,
        ): ClientExceptionSetBinding => unwrap(response),
      }),
    }),
  })

export const {
  useListApiClientsQuery,
  useListApiClientSecretsQuery,
  useCreateApiClientMutation,
  useUpdateApiClientMutation,
  useDeleteApiClientMutation,
  useRotateApiClientSecretMutation,
  useRetireApiClientSecretMutation,
  useRevealApiClientSecretMutation,
  useGetEffectivePermissionsQuery,
  useAssignClientRoleMutation,
  useRemoveClientRoleMutation,
  useListClientExceptionSetsQuery,
  useBindClientExceptionSetMutation,
  useUnbindClientExceptionSetMutation,
} = apiClientApi
