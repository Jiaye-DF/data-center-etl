import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

export interface SyncTablePayload {
  schema: string
  table: string
}

/** 篩選同步請求:schema + 進階篩選條件(截止日空字串代表未設,由呼叫端過濾) */
export interface SyncFilteredPayload {
  schema: string
  rows: 'all' | 'nonempty' | 'empty'
  synced: 'all' | 'synced' | 'unsynced'
  transformed: 'all' | 'transformed' | 'untransformed'
  syncedBefore: string
  transformedBefore: string
  keyword: string
}

/** 同步觸發結果:filtered 範圍會回符合並送出的表數 matched */
export interface SyncTriggerResult {
  task_id: string
  run_uid: string | null
  scope: string
  matched: number | null
}

/** RDS → 資料中心手動同步觸發(require_admin) */
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
    syncFiltered: build.mutation<SyncTriggerResult, SyncFilteredPayload>({
      query: ({
        schema,
        rows,
        synced,
        transformed,
        syncedBefore,
        transformedBefore,
        keyword,
      }) => ({
        url: '/sync/filtered',
        method: 'POST',
        body: {
          schema,
          rows,
          synced,
          transformed,
          ...(syncedBefore !== '' ? { synced_before: syncedBefore } : {}),
          ...(transformedBefore !== ''
            ? { transformed_before: transformedBefore }
            : {}),
          ...(keyword !== '' ? { keyword } : {}),
        },
      }),
      transformResponse: (
        response: ApiEnvelope<SyncTriggerResult>,
      ): SyncTriggerResult => unwrap(response),
    }),
  }),
})

export const {
  useSyncTableMutation,
  useSyncAllMutation,
  useSyncFilteredMutation,
} = syncApi
