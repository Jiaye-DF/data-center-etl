import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** run 狀態(對齊 backend etl_runs.status check constraint;partial 已移除) */
export type RunStatus = 'pending' | 'running' | 'success' | 'failed'
/** 逐表 log 狀態(對齊 backend etl_run_logs.status check constraint) */
export type RunLogStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped'
export type TriggerType = 'schedule' | 'manual'

export interface RunSummary {
  uid: string
  trigger_type: string
  status: string
  schedule_uid: string | null
  schedule_name: string | null
  started_at: string | null
  finished_at: string | null
  total_tables: number
  success_tables: number
  failed_tables: number
  error_message: string | null
  created_at: string
}

export interface RunListData {
  items: RunSummary[]
  total: number
  page: number
  page_size: number
}

export interface RunListParams {
  page: number
  pageSize: number
  status?: RunStatus
  triggerType?: TriggerType
}

export interface RunLog {
  uid: string
  etl_table_uid: string | null
  source_schema: string
  source_table: string
  status: string
  row_count: number | null
  duration_ms: number | null
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  error_stack: string | null
}

export interface RunLogListData {
  items: RunLog[]
  total: number
  page: number
  page_size: number
}

export interface RunLogListParams {
  runUid: string
  page: number
  pageSize: number
  status?: RunLogStatus
}

export interface RunTriggerPayload {
  /** NULL 表示對全部啟用表執行一輪;指定則只跑該表 */
  etlTableUid: string | null
}

export interface RunTriggerResult {
  task_id: string
  /** 佇列模式下 run 由 worker 建立,enqueue 當下尚無 run → null */
  run_uid: string | null
}

export const runApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['Run', 'RunLog'] })
  .injectEndpoints({
    endpoints: (build) => ({
      listRuns: build.query<RunListData, RunListParams>({
        query: ({ page, pageSize, status, triggerType }) => ({
          url: '/runs',
          // fetchBaseQuery 會自動剔除 undefined 參數
          params: { page, page_size: pageSize, status, trigger_type: triggerType },
        }),
        providesTags: [{ type: 'Run', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<RunListData>): RunListData =>
          unwrap(response),
      }),
      getRun: build.query<RunSummary, string>({
        query: (uid) => `/runs/${uid}`,
        providesTags: (_result, _error, uid) => [{ type: 'Run', id: uid }],
        transformResponse: (response: ApiEnvelope<RunSummary>): RunSummary =>
          unwrap(response),
      }),
      listRunLogs: build.query<RunLogListData, RunLogListParams>({
        query: ({ runUid, page, pageSize, status }) => ({
          url: `/runs/${runUid}/logs`,
          params: { page, page_size: pageSize, status },
        }),
        providesTags: (_result, _error, { runUid }) => [
          { type: 'RunLog', id: runUid },
        ],
        transformResponse: (
          response: ApiEnvelope<RunLogListData>,
        ): RunLogListData => unwrap(response),
      }),
      // 手動觸發:成功後 invalidate run 清單,讓新 run 即時反映
      triggerRun: build.mutation<RunTriggerResult, RunTriggerPayload>({
        query: ({ etlTableUid }) => ({
          url: '/runs/trigger',
          method: 'POST',
          body: { etl_table_uid: etlTableUid },
        }),
        invalidatesTags: [{ type: 'Run', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<RunTriggerResult>,
        ): RunTriggerResult => unwrap(response),
      }),
    }),
  })

export const {
  useListRunsQuery,
  useGetRunQuery,
  useListRunLogsQuery,
  useTriggerRunMutation,
} = runApi
