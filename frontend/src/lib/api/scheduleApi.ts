import { baseApi } from '@/lib/api/baseApi'

/**
 * 後端統一回應信封(FastAPI `ApiResponse[T]`)。
 * etlConfigApi.ts(task-010 檔)內另有私有同構定義,該檔不可動;
 * 本檔匯出供 runApi.ts 共用,抽至 lib/api 共用檔為後續正式化候選(見 fixed.md)。
 */
export interface ApiEnvelope<T> {
  success: boolean
  data: T | null
  detail: string | null
  response_code: number
}

export function unwrapEnvelope<T>(envelope: ApiEnvelope<T>): T {
  if (envelope.data === null) {
    throw new Error(envelope.detail ?? 'empty_response')
  }
  return envelope.data
}

export interface Schedule {
  uid: string
  name: string
  cron_expr: string
  is_enabled: boolean
  /** NULL 表示對全部啟用表執行(對齊 backend schedules.etl_table_pid 語意) */
  etl_table_uid: string | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface ScheduleListData {
  items: Schedule[]
  total: number
  page: number
  page_size: number
}

export interface ScheduleListParams {
  page: number
  pageSize: number
}

export interface ScheduleCreatePayload {
  name: string
  cron_expr: string
  is_enabled: boolean
  etl_table_uid: string | null
  description: string | null
}

export interface ScheduleUpdatePayload {
  uid: string
  name: string
  cron_expr: string
  etl_table_uid: string | null
  description: string | null
}

export interface ScheduleSetEnabledPayload {
  uid: string
  enabled: boolean
}

interface ScheduleDeleteData {
  message: string
}

export const scheduleApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['Schedule'] })
  .injectEndpoints({
    endpoints: (build) => ({
      listSchedules: build.query<ScheduleListData, ScheduleListParams>({
        query: ({ page, pageSize }) => ({
          url: '/schedules',
          params: { page, page_size: pageSize },
        }),
        providesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ScheduleListData>,
        ): ScheduleListData => unwrapEnvelope(response),
      }),
      createSchedule: build.mutation<Schedule, ScheduleCreatePayload>({
        query: (payload) => ({
          url: '/schedules',
          method: 'POST',
          body: payload,
        }),
        invalidatesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<Schedule>): Schedule =>
          unwrapEnvelope(response),
      }),
      updateSchedule: build.mutation<Schedule, ScheduleUpdatePayload>({
        query: ({ uid, ...body }) => ({
          url: `/schedules/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<Schedule>): Schedule =>
          unwrapEnvelope(response),
      }),
      deleteSchedule: build.mutation<ScheduleDeleteData, string>({
        query: (uid) => ({
          url: `/schedules/${uid}`,
          method: 'DELETE',
        }),
        invalidatesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ScheduleDeleteData>,
        ): ScheduleDeleteData => unwrapEnvelope(response),
      }),
      setScheduleEnabled: build.mutation<Schedule, ScheduleSetEnabledPayload>({
        query: ({ uid, enabled }) => ({
          url: `/schedules/${uid}/${enabled ? 'enable' : 'disable'}`,
          method: 'POST',
        }),
        invalidatesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<Schedule>): Schedule =>
          unwrapEnvelope(response),
      }),
    }),
  })

export const {
  useListSchedulesQuery,
  useCreateScheduleMutation,
  useUpdateScheduleMutation,
  useDeleteScheduleMutation,
  useSetScheduleEnabledMutation,
} = scheduleApi
