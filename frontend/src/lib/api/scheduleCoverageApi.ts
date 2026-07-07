import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** 納入狀態篩選 */
export type CoverageInclusion = 'all' | 'included' | 'excluded'
/** 上次結果篩選 */
export type CoverageLastResult = 'all' | 'success' | 'failed' | 'never'

/** 目前啟用排程資訊(名稱 + cron) */
export interface CoverageScheduleInfo {
  name: string
  cron_expr: string
}

/** schema 分頁籤摘要 */
export interface SchemaCoverageSummary {
  schema_name: string
  table_count: number
  excluded_count: number
}

/** 依表檢視的單列 */
export interface TableCoverageItem {
  uid: string
  schema_name: string
  table_name: string
  business_name: string | null
  sync_excluded: boolean
  included: boolean
  last_synced_at: string | null
  last_run_status: string | null
  row_count: number
}

/** GET /schedule-coverage/schemas 回傳 */
export interface CoverageSchemasData {
  items: SchemaCoverageSummary[]
  has_enabled_schedule: boolean
  schedules: CoverageScheduleInfo[]
}

/** GET /schedule-coverage 回傳 */
export interface CoverageListData {
  items: TableCoverageItem[]
  total: number
  page: number
  page_size: number
  schedules: CoverageScheduleInfo[]
  has_enabled_schedule: boolean
}

export interface CoverageListParams {
  schema: string
  page: number
  pageSize: number
  inclusion: CoverageInclusion
  lastResult: CoverageLastResult
  keyword: string
}

export interface SetTableExclusionPayload {
  uid: string
  excluded: boolean
}

const LIST_TAG = { type: 'ScheduleCoverage' as const, id: 'LIST' }
const SCHEMAS_TAG = { type: 'ScheduleCoverage' as const, id: 'SCHEMAS' }

export const scheduleCoverageApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['ScheduleCoverage'] })
  .injectEndpoints({
    endpoints: (build) => ({
      getCoverageSchemas: build.query<CoverageSchemasData, void>({
        query: () => ({ url: '/schedule-coverage/schemas' }),
        providesTags: [SCHEMAS_TAG],
        transformResponse: (
          response: ApiEnvelope<CoverageSchemasData>,
        ): CoverageSchemasData => unwrap(response),
      }),
      listCoverageTables: build.query<CoverageListData, CoverageListParams>({
        query: ({ schema, page, pageSize, inclusion, lastResult, keyword }) => ({
          url: '/schedule-coverage',
          params: {
            schema,
            page,
            page_size: pageSize,
            inclusion,
            last_result: lastResult,
            keyword,
          },
        }),
        providesTags: [LIST_TAG],
        transformResponse: (
          response: ApiEnvelope<CoverageListData>,
        ): CoverageListData => unwrap(response),
      }),
      setTableExclusion: build.mutation<
        TableCoverageItem,
        SetTableExclusionPayload
      >({
        query: ({ uid, excluded }) => ({
          url: `/schedule-coverage/tables/${uid}/exclusion`,
          method: 'PATCH',
          body: { excluded },
        }),
        invalidatesTags: [LIST_TAG, SCHEMAS_TAG],
        transformResponse: (
          response: ApiEnvelope<TableCoverageItem>,
        ): TableCoverageItem => unwrap(response),
      }),
    }),
  })

export const {
  useGetCoverageSchemasQuery,
  useListCoverageTablesQuery,
  useSetTableExclusionMutation,
} = scheduleCoverageApi
