import { baseApi } from '@/lib/api/baseApi'
import type { ApiEnvelope } from '@/types/api'

export interface SyncTablePayload {
  schema: string
  table: string
}

/** RDS → 資料中心手動同步觸發(require_admin,回應僅需 success 旗標) */
export const syncApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    syncTable: build.mutation<boolean, SyncTablePayload>({
      query: (payload) => ({
        url: '/sync/table',
        method: 'POST',
        body: payload,
      }),
      transformResponse: (response: ApiEnvelope<unknown>): boolean =>
        response.success,
    }),
    syncAll: build.mutation<boolean, void>({
      query: () => ({
        url: '/sync/all',
        method: 'POST',
      }),
      transformResponse: (response: ApiEnvelope<unknown>): boolean =>
        response.success,
    }),
  }),
})

export const { useSyncTableMutation, useSyncAllMutation } = syncApi
