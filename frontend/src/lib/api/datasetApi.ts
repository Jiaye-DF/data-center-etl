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
  /** pg_class.reltuples 估算;未 ANALYZE 的表為 -1(未知) */
  row_estimate: number
}

export interface DatasetTableListData {
  items: TableSummary[]
  total: number
  page: number
  page_size: number
}

export interface ColumnInfo {
  name: string
  data_type: string
  nullable: boolean
  ordinal_position: number
}

export interface ListTablesParams {
  dataset: Dataset
  schema: string
  page: number
  pageSize: number
}

export interface ListColumnsParams {
  dataset: Dataset
  schema: string
  table: string
}

export const datasetApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listDatasetSchemas: build.query<SchemaSummary[], Dataset>({
      query: (dataset) => `/datasets/${dataset}/schemas`,
      transformResponse: (
        response: ApiEnvelope<{ items: SchemaSummary[] }>,
      ): SchemaSummary[] => unwrap(response).items,
    }),
    listDatasetTables: build.query<DatasetTableListData, ListTablesParams>({
      query: ({ dataset, schema, page, pageSize }) => ({
        url: `/datasets/${dataset}/tables`,
        params: { schema, page, page_size: pageSize },
      }),
      transformResponse: (
        response: ApiEnvelope<DatasetTableListData>,
      ): DatasetTableListData => unwrap(response),
    }),
    listDatasetColumns: build.query<ColumnInfo[], ListColumnsParams>({
      query: ({ dataset, schema, table }) => ({
        url: `/datasets/${dataset}/tables/${schema}/${table}/columns`,
      }),
      transformResponse: (
        response: ApiEnvelope<{ columns: ColumnInfo[] }>,
      ): ColumnInfo[] => unwrap(response).columns,
    }),
  }),
})

export const {
  useListDatasetSchemasQuery,
  useListDatasetTablesQuery,
  useListDatasetColumnsQuery,
} = datasetApi
