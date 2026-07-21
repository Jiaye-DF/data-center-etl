import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'
import type { SnapshotRefreshProgress } from '@/lib/api/datasetApi'
import type { ActiveRunData } from '@/lib/api/runApi'

/** 全局進度聚合(AD-121):sync / snapshot(source、target)/ apply 一次輪詢取回,layout 只掛一條 */
export interface GlobalProgress {
  /** 執行中 ETL run 進度(與 GET /runs/active 的 data 同型);無執行中 run 為 null */
  sync: ActiveRunData | null
  snapshot_source: SnapshotRefreshProgress
  snapshot_target: SnapshotRefreshProgress
  apply: SnapshotRefreshProgress
}

export const progressApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // 全局進度:進度條輪詢用(閒置時各欄 active=false / sync=null),不掛 tag
    globalProgress: build.query<GlobalProgress, void>({
      query: () => '/progress',
      transformResponse: (
        response: ApiEnvelope<GlobalProgress>,
      ): GlobalProgress => unwrap(response),
    }),
  }),
})

export const { useGlobalProgressQuery } = progressApi
