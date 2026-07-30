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

export const apiClientApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['ApiClient'] })
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
    }),
  })

export const {
  useListApiClientsQuery,
  useListApiClientSecretsQuery,
  useCreateApiClientMutation,
  useUpdateApiClientMutation,
  useRotateApiClientSecretMutation,
  useRetireApiClientSecretMutation,
  useRevealApiClientSecretMutation,
} = apiClientApi
