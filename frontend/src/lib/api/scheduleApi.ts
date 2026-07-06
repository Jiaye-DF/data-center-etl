import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

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
        ): ScheduleListData => unwrap(response),
      }),
      createSchedule: build.mutation<Schedule, ScheduleCreatePayload>({
        query: (payload) => ({
          url: '/schedules',
          method: 'POST',
          body: payload,
        }),
        invalidatesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<Schedule>): Schedule =>
          unwrap(response),
      }),
      updateSchedule: build.mutation<Schedule, ScheduleUpdatePayload>({
        query: ({ uid, ...body }) => ({
          url: `/schedules/${uid}`,
          method: 'PATCH',
          body,
        }),
        invalidatesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<Schedule>): Schedule =>
          unwrap(response),
      }),
      deleteSchedule: build.mutation<ScheduleDeleteData, string>({
        query: (uid) => ({
          url: `/schedules/${uid}`,
          method: 'DELETE',
        }),
        invalidatesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (
          response: ApiEnvelope<ScheduleDeleteData>,
        ): ScheduleDeleteData => unwrap(response),
      }),
      setScheduleEnabled: build.mutation<Schedule, ScheduleSetEnabledPayload>({
        query: ({ uid, enabled }) => ({
          url: `/schedules/${uid}/${enabled ? 'enable' : 'disable'}`,
          method: 'POST',
        }),
        invalidatesTags: [{ type: 'Schedule', id: 'LIST' }],
        transformResponse: (response: ApiEnvelope<Schedule>): Schedule =>
          unwrap(response),
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
