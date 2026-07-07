import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

export interface Schedule {
  uid: string
  name: string
  cron_expr: string
  is_enabled: boolean
  /** 固定文案「增量同步全部表」(v1.3 起排程只有一種:全表增量) */
  job_desc: string
  /** 上次執行狀態:success/failed/partial/running/pending;null=未跑 */
  last_run_status: string | null
  last_run_finished_at: string | null
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
  description: string | null
}

export interface ScheduleUpdatePayload {
  uid: string
  name: string
  cron_expr: string
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
