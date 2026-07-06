import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** 資料集:source = 原始(erp_migration_test)、target = ETL 轉換後(erp_etl_hub_test) */
export type Dataset = 'source' | 'target'

export interface SchemaSummary {
  schema: string
  table_count: number
}

export interface TableSummary {
  name: string
  column_count: number
  /** bounded row 數(SELECT 1 … LIMIT 1001 探測);> 1000 代表超過上限,顯示 1000+ */
  row_count: number
  /** 業務資料中文名(快照時 JOIN DS 字典 GAT_FILE 落地,非即時查 RDS);無對應則為 null */
  business_name: string | null
  /** 最近一次 RDS 同步時間(ISO,naive UTC+8);尚未同步為 null */
  last_synced_at: string | null
  /** 最近一次 ETL 轉換時間(ISO,naive UTC+8);尚未轉換為 null */
  last_transformed_at: string | null
}

export interface DatasetTableListData {
  items: TableSummary[]
  total: number
  page: number
  page_size: number
}

export interface ListTablesParams {
  dataset: Dataset
  schema: string
  page: number
  pageSize: number
  /** 過濾資料筆數 = 0 的表;預設 true(呼叫端需明確帶入) */
  hideEmpty: boolean
}

export const datasetApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['DatasetSchema', 'DatasetTable'] })
  .injectEndpoints({
    endpoints: (build) => ({
      listDatasetSchemas: build.query<SchemaSummary[], Dataset>({
        query: (dataset) => `/datasets/${dataset}/schemas`,
        providesTags: (_result, _error, dataset) => [
          { type: 'DatasetSchema', id: dataset },
        ],
        transformResponse: (
          response: ApiEnvelope<{ items: SchemaSummary[] }>,
        ): SchemaSummary[] => unwrap(response).items,
      }),
      listDatasetTables: build.query<DatasetTableListData, ListTablesParams>({
        query: ({ dataset, schema, page, pageSize, hideEmpty }) => ({
          url: `/datasets/${dataset}/tables`,
          params: {
            schema,
            page,
            page_size: pageSize,
            hide_empty: hideEmpty,
          },
        }),
        providesTags: (_result, _error, { dataset }) => [
          { type: 'DatasetTable', id: dataset },
        ],
        transformResponse: (
          response: ApiEnvelope<DatasetTableListData>,
        ): DatasetTableListData => unwrap(response),
      }),
      // 重整快照:對 RDS 重新內省 + JOIN 業務名稱寫回自有 DB,成功後兩個查詢皆需重抓
      refreshDatasetSnapshot: build.mutation<boolean, Dataset>({
        query: (dataset) => ({
          url: `/datasets/${dataset}/snapshot/refresh`,
          method: 'POST',
        }),
        invalidatesTags: (_result, _error, dataset) => [
          { type: 'DatasetSchema', id: dataset },
          { type: 'DatasetTable', id: dataset },
        ],
        transformResponse: (response: ApiEnvelope<unknown>): boolean =>
          response.success,
      }),
    }),
  })

export const {
  useListDatasetSchemasQuery,
  useListDatasetTablesQuery,
  useRefreshDatasetSnapshotMutation,
} = datasetApi
