import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** 逐表執行狀態(對齊 backend `etl_run_logs.status` check constraint) */
export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped'

export interface EtlMapping {
  uid: string
  source_column: string
  target_column: string
  transform_type: string | null
  comment: string
  sort_order: number
}

/** mapping 全量更新單筆(PUT /etl-tables/{uid}/mappings) */
export interface EtlMappingUpsert {
  source_column: string
  target_column: string
  transform_type: string | null
  comment: string | null
  sort_order: number
}

export interface EtlTableSummary {
  uid: string
  source_schema: string
  source_table: string
  target_schema: string
  target_table: string
  is_enabled: boolean
  description: string | null
  mapping_count: number
  last_run_status: string | null
  last_run_at: string | null
}

export interface EtlTableDetail extends EtlTableSummary {
  mappings: EtlMapping[]
}

export interface EtlTableListData {
  items: EtlTableSummary[]
  total: number
  page: number
  page_size: number
}

export interface EtlTableListParams {
  page: number
  pageSize: number
}

export interface SetEnabledPayload {
  uid: string
  enabled: boolean
}

export interface ReplaceMappingsPayload {
  uid: string
  mappings: EtlMappingUpsert[]
}

export const etlConfigApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['EtlTable'] })
  .injectEndpoints({
    endpoints: (build) => ({
      listEtlTables: build.query<EtlTableListData, EtlTableListParams>({
        query: ({ page, pageSize }) => ({
          url: '/etl-tables',
          params: { page, page_size: pageSize },
        }),
        providesTags: [{ type: 'EtlTable', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<EtlTableListData>,
        ): EtlTableListData => unwrap(response),
      }),
      getEtlTable: build.query<EtlTableDetail, string>({
        query: (uid) => `/etl-tables/${uid}`,
        providesTags: (_result, _error, uid) => [{ type: 'EtlTable', id: uid }],
        transformResponse: (
          response: ApiEnvelope<EtlTableDetail>,
        ): EtlTableDetail => unwrap(response),
      }),
      setEtlTableEnabled: build.mutation<EtlTableDetail, SetEnabledPayload>({
        query: ({ uid, enabled }) => ({
          url: `/etl-tables/${uid}/${enabled ? 'enable' : 'disable'}`,
          method: 'POST',
        }),
        invalidatesTags: (_result, _error, { uid }) => [
          { type: 'EtlTable', id: 'LIST' },
          { type: 'EtlTable', id: uid },
        ],
        transformResponse: (
          response: ApiEnvelope<EtlTableDetail>,
        ): EtlTableDetail => unwrap(response),
      }),
      replaceEtlTableMappings: build.mutation<
        EtlTableDetail,
        ReplaceMappingsPayload
      >({
        query: ({ uid, mappings }) => ({
          url: `/etl-tables/${uid}/mappings`,
          method: 'PUT',
          body: { mappings },
        }),
        invalidatesTags: (_result, _error, { uid }) => [
          { type: 'EtlTable', id: 'LIST' },
          { type: 'EtlTable', id: uid },
        ],
        transformResponse: (
          response: ApiEnvelope<EtlTableDetail>,
        ): EtlTableDetail => unwrap(response),
      }),
    }),
  })

export const {
  useListEtlTablesQuery,
  useGetEtlTableQuery,
  useSetEtlTableEnabledMutation,
  useReplaceEtlTableMappingsMutation,
} = etlConfigApi
