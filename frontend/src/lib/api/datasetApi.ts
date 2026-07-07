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

/** 資料總筆數篩選:全部 / 僅有資料(>0)/ 僅空表(=0) */
export type RowsFilter = 'all' | 'nonempty' | 'empty'
/** RDS 同步狀態:全部 / 已同步(有時間)/ 未同步(無時間) */
export type SyncedFilter = 'all' | 'synced' | 'unsynced'
/** ETL 轉換狀態:全部 / 已轉換(有時間)/ 未轉換(無時間) */
export type TransformedFilter = 'all' | 'transformed' | 'untransformed'

/** 進階篩選狀態(狀態分段 + 截止日 YYYY-MM-DD;空字串代表未設)
 *  截止日搭配狀態 → 「是否在該日前(含)同步/轉換」 */
export interface TableFilters {
  rows: RowsFilter
  synced: SyncedFilter
  transformed: TransformedFilter
  syncedBefore: string
  transformedBefore: string
  /** 對 table_name 或 business_name 做子字串比對(空字串不套) */
  keyword: string
  /** true=keyword 為下拉選定表名(精準等值);false=自由輸入(子字串模糊) */
  keywordExact: boolean
}

export interface ListTablesParams extends TableFilters {
  dataset: Dataset
  schema: string
  page: number
  pageSize: number
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
        query: ({
          dataset,
          schema,
          page,
          pageSize,
          rows,
          synced,
          transformed,
          syncedBefore,
          transformedBefore,
          keyword,
          keywordExact,
        }) => ({
          url: `/datasets/${dataset}/tables`,
          params: {
            schema,
            page,
            page_size: pageSize,
            rows,
            synced,
            transformed,
            // 截止日 / 關鍵字僅在有值時帶上,避免送空字串;精準等值一併帶 keyword_exact
            ...(syncedBefore !== '' ? { synced_before: syncedBefore } : {}),
            ...(transformedBefore !== ''
              ? { transformed_before: transformedBefore }
              : {}),
            ...(keyword !== '' ? { keyword, keyword_exact: keywordExact } : {}),
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
