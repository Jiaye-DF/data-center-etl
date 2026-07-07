import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** 最新一筆 run 摘要 */
export interface DashboardLatestRun {
  uid: string
  trigger_type: string
  status: string
  total_tables: number
  success_tables: number
  failed_tables: number
  finished_at: string | null
}

/** 同步健康:最新 run + 近 N 筆成功/失敗數 */
export interface DashboardSyncHealth {
  latest_run: DashboardLatestRun | null
  recent_total: number
  recent_success: number
  recent_failed: number
}

export interface DashboardFailedTable {
  source_schema: string
  source_table: string
  error_message: string | null
}

/** 待處理失敗表:最新 run 有失敗時列出(可點進該 run log) */
export interface DashboardPendingFailures {
  run_uid: string | null
  items: DashboardFailedTable[]
}

/** 排程概況:啟用數 / 總表數 / 啟用中相異 cron(前端算最近一班) */
export interface DashboardSchedules {
  enabled_count: number
  table_total: number
  enabled_cron_exprs: string[]
}

/** 單一資料集規模 + 快照新鮮度 */
export interface DashboardDatasetScale {
  dataset: string
  table_count: number
  nonempty_count: number
  empty_count: number
  last_snapshot_at: string | null
  last_synced_at: string | null
}

export interface DashboardOverview {
  sync_health: DashboardSyncHealth
  pending_failures: DashboardPendingFailures
  schedules: DashboardSchedules
  datasets: DashboardDatasetScale[]
}

export const dashboardApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    dashboardOverview: build.query<DashboardOverview, void>({
      query: () => '/dashboard/overview',
      transformResponse: (
        response: ApiEnvelope<DashboardOverview>,
      ): DashboardOverview => unwrap(response),
    }),
  }),
})

export const { useDashboardOverviewQuery } = dashboardApi
