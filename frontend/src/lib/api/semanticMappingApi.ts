import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** 審核狀態:draft(草稿)/ confirmed(已複核,進 view / JSON key) */
export type MappingStatus = 'draft' | 'confirmed'
export type MappingStatusFilter = 'all' | MappingStatus

export interface SemanticMappingItem {
  table_name: string
  /** 空字串代表表層級映射(view 名依據) */
  column_name: string
  english_name: string
  zh_name: string | null
  status: MappingStatus
  updated_by: string | null
  /** naive UTC+8(ISO) */
  updated_at: string
}

export interface SemanticMappingListData {
  items: SemanticMappingItem[]
  total: number
  page: number
  page_size: number
}

export interface SemanticTableSummary {
  table_name: string
  draft_count: number
  confirmed_count: number
  /** 表層級中文名(無表層級列為 null) */
  zh_name: string | null
  /** 表層級英文語意名(無表層級列為 null) */
  english_name: string | null
}

export interface ListSemanticMappingsParams {
  /** 表名精準篩選;空字串不篩 */
  table: string
  status: MappingStatusFilter
  /** 欄名 / 英文名 / 中文名子字串;空字串不篩 */
  keyword: string
  page: number
  pageSize: number
}

export interface UpdateSemanticMappingPayload {
  table_name: string
  column_name: string
  english_name?: string
  zh_name?: string | null
  status?: MappingStatus
}

/** 「套用變更」受理結果(202):後端改背景執行,進度由全局進度條(GET /progress 的 apply)呈現 */
export interface SyncViewsQueued {
  queued: boolean
}

export const semanticMappingApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['SemanticMapping'] })
  .injectEndpoints({
    endpoints: (build) => ({
      listSemanticMappings: build.query<
        SemanticMappingListData,
        ListSemanticMappingsParams
      >({
        query: ({ table, status, keyword, page, pageSize }) => ({
          url: '/semantic-mappings',
          params: {
            page,
            page_size: pageSize,
            status,
            ...(table !== '' ? { table } : {}),
            ...(keyword !== '' ? { keyword } : {}),
          },
        }),
        providesTags: ['SemanticMapping'],
        transformResponse: (
          response: ApiEnvelope<SemanticMappingListData>,
        ): SemanticMappingListData => unwrap(response),
      }),
      listSemanticTables: build.query<SemanticTableSummary[], void>({
        query: () => '/semantic-mappings/tables',
        providesTags: ['SemanticMapping'],
        transformResponse: (
          response: ApiEnvelope<{ items: SemanticTableSummary[] }>,
        ): SemanticTableSummary[] => unwrap(response).items,
      }),
      updateSemanticMapping: build.mutation<
        SemanticMappingItem,
        UpdateSemanticMappingPayload
      >({
        query: (payload) => ({
          url: '/semantic-mappings',
          method: 'PATCH',
          body: payload,
        }),
        invalidatesTags: ['SemanticMapping'],
        transformResponse: (
          response: ApiEnvelope<SemanticMappingItem>,
        ): SemanticMappingItem => unwrap(response),
      }),
      confirmSemanticTable: build.mutation<{ affected: number }, string>({
        query: (tableName) => ({
          url: '/semantic-mappings/confirm-table',
          method: 'POST',
          body: { table_name: tableName },
        }),
        invalidatesTags: ['SemanticMapping'],
        transformResponse: (
          response: ApiEnvelope<{ affected: number }>,
        ): { affected: number } => unwrap(response),
      }),
      syncSemanticViews: build.mutation<SyncViewsQueued, void>({
        query: () => ({ url: '/semantic-mappings/sync-views', method: 'POST' }),
        transformResponse: (
          response: ApiEnvelope<SyncViewsQueued>,
        ): SyncViewsQueued => unwrap(response),
      }),
    }),
  })

export const {
  useListSemanticMappingsQuery,
  useListSemanticTablesQuery,
  useUpdateSemanticMappingMutation,
  useConfirmSemanticTableMutation,
  useSyncSemanticViewsMutation,
} = semanticMappingApi
