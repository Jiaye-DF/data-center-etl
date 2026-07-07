import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

/** 啟停過濾:全部 / 已啟用 / 已停用 */
export type EnabledFilter = 'all' | 'enabled' | 'disabled'
/** 上次結果過濾:全部 / 成功 / 失敗 / 從未執行 */
export type LastResultFilter = 'all' | 'success' | 'failed' | 'never'
/** 資料總筆數過濾:全部 / 有資料(>0)/ 空表(=0) */
export type RowsFilter = 'all' | 'nonempty' | 'empty'

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
  /** true=keyword 為下拉選定表名(精準等值);false=自由輸入(子字串模糊) */
  keywordExact: boolean
  /** 資料總筆數:全部 / 有資料 / 空表 */
  rows: RowsFilter
  /** 排程時段起(HH:MM,含);空字串=不限 */
  timeFrom: string
  /** 排程時段迄(HH:MM,含);空字串=不限 */
  timeTo: string
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

/**
 * 批次啟停:省略 schema 與所有 filter_* 代表全部來源表排程;
 * 帶篩選則僅作用於逐表列表命中的表(對齊進階篩選)。
 */
export interface ScheduleBatchEnabledPayload {
  enabled: boolean
  schema?: string
  filter_enabled?: EnabledFilter
  filter_last_result?: LastResultFilter
  filter_keyword?: string
  /** true=filter_keyword 為下拉選定表名(精準等值);false=子字串模糊 */
  filter_keyword_exact?: boolean
  /** 資料總筆數:all / nonempty / empty */
  filter_rows?: RowsFilter
  /** 排程時段起(HH:MM,含);省略=不限 */
  filter_time_from?: string
  /** 排程時段迄(HH:MM,含);省略=不限 */
  filter_time_to?: string
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
        query: ({
          schema,
          page,
          pageSize,
          enabled,
          lastResult,
          keyword,
          keywordExact,
          rows,
          timeFrom,
          timeTo,
        }) => ({
          url: '/schedules',
          params: {
            schema,
            page,
            page_size: pageSize,
            enabled,
            last_result: lastResult,
            rows,
            // 關鍵字 / 時段僅在有值時帶上,避免送空字串;精準等值一併帶 exact
            ...(keyword !== '' ? { keyword, exact: keywordExact } : {}),
            ...(timeFrom !== '' ? { time_from: timeFrom } : {}),
            ...(timeTo !== '' ? { time_to: timeTo } : {}),
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
