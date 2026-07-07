import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** 啟停過濾:全部 / 已啟用 / 已停用 */
export type EnabledFilter = 'all' | 'enabled' | 'disabled'
/** 上次結果過濾:全部 / 成功 / 失敗 / 從未執行 */
export type LastResultFilter = 'all' | 'success' | 'failed' | 'never'

/** 逐表視角一列:來源表 meta × 其排程 × 最新執行結果(LEFT JOIN,尚無排程之欄位為 null) */
export interface ScheduleTableView {
  table_name: string
  business_name: string | null
  schedule_uid: string | null
  cron_expr: string | null
  is_enabled: boolean | null
  description: string | null
  last_synced_at: string | null
  last_run_status: string | null
}

export interface ScheduleTableListData {
  items: ScheduleTableView[]
  total: number
  page: number
  page_size: number
}

export interface ScheduleTableListParams {
  /** 來源表 schema(必填) */
  schema: string
  page: number
  pageSize: number
  enabled: EnabledFilter
  lastResult: LastResultFilter
  keyword: string
}

/** 各 schema 摘要(來源表數 / 已啟用排程數) */
export interface ScheduleSchemaSummary {
  schema_name: string
  table_count: number
  enabled_count: number
}

/** 單一排程完整回應(PATCH / enable / disable 回傳) */
export interface ScheduleResponse {
  uid: string
  name: string
  cron_expr: string
  is_enabled: boolean
  job_desc: string
  last_run_status: string | null
  last_run_finished_at: string | null
  description: string | null
  created_at: string
  updated_at: string
}

/** 更新排程:僅 cron / 啟停 / 描述(不改則省略對應欄) */
export interface ScheduleUpdatePayload {
  uid: string
  cron_expr?: string
  is_enabled?: boolean
  description?: string | null
}

export interface ScheduleSetEnabledPayload {
  uid: string
  enabled: boolean
}

/** 批次啟停:省略 schema 代表全部來源表排程 */
export interface ScheduleBatchEnabledPayload {
  enabled: boolean
  schema?: string
}

export interface ScheduleBatchEnabledResult {
  affected: number
}

export const scheduleApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['ScheduleTable', 'ScheduleSchema'] })
  .injectEndpoints({
    endpoints: (build) => ({
      listScheduleTables: build.query<
        ScheduleTableListData,
        ScheduleTableListParams
      >({
        query: ({ schema, page, pageSize, enabled, lastResult, keyword }) => ({
          url: '/schedules',
          params: {
            schema,
            page,
            page_size: pageSize,
            enabled,
            last_result: lastResult,
            // 關鍵字僅在有值時帶上,避免送空字串
            ...(keyword !== '' ? { keyword } : {}),
          },
        }),
        providesTags: [{ type: 'ScheduleTable', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ScheduleTableListData>,
        ): ScheduleTableListData => unwrap(response),
      }),
      getScheduleSchemas: build.query<ScheduleSchemaSummary[], void>({
        query: () => '/schedules/schemas',
        providesTags: [{ type: 'ScheduleSchema', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<{ items: ScheduleSchemaSummary[] }>,
        ): ScheduleSchemaSummary[] => unwrap(response).items,
      }),
      updateSchedule: build.mutation<ScheduleResponse, ScheduleUpdatePayload>({
        query: ({ uid, ...body }) => ({
          url: `/schedules/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [
          { type: 'ScheduleTable', id: 'LIST' },
          { type: 'ScheduleSchema', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<ScheduleResponse>,
        ): ScheduleResponse => unwrap(response),
      }),
      setScheduleEnabled: build.mutation<
        ScheduleResponse,
        ScheduleSetEnabledPayload
      >({
        query: ({ uid, enabled }) => ({
          url: `/schedules/${uid}/${enabled ? 'enable' : 'disable'}`,
          method: 'POST',
        }),
        invalidatesTags: [
          { type: 'ScheduleTable', id: 'LIST' },
          { type: 'ScheduleSchema', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<ScheduleResponse>,
        ): ScheduleResponse => unwrap(response),
      }),
      batchSetEnabled: build.mutation<
        ScheduleBatchEnabledResult,
        ScheduleBatchEnabledPayload
      >({
        query: (body) => ({
          url: '/schedules/batch-enabled',
          method: 'POST',
          body,
        }),
        invalidatesTags: [
          { type: 'ScheduleTable', id: 'LIST' },
          { type: 'ScheduleSchema', id: 'LIST' },
        ],
        transformResponse: (
          response: ApiEnvelope<ScheduleBatchEnabledResult>,
        ): ScheduleBatchEnabledResult => unwrap(response),
      }),
    }),
  })

export const {
  useListScheduleTablesQuery,
  useGetScheduleSchemasQuery,
  useUpdateScheduleMutation,
  useSetScheduleEnabledMutation,
  useBatchSetEnabledMutation,
} = scheduleApi
