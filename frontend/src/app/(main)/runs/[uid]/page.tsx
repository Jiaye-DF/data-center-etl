'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useGetRunQuery } from '@/lib/api/runApi'
import { RunLogTable } from '@/components/runs/RunLogTable'
import { StatusBadge } from '@/components/common/StatusBadge'
import {
  AutoRefreshControl,
  useLastUpdatedAt,
} from '@/components/common/AutoRefreshControl'
import { TRIGGER_TYPE_LABELS } from '@/constants/labels'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime, formatNullableDateTime } from '@/utils/datetime'

// run 執行中時 5s 輪詢摘要,結束(success/failed)即停;視窗未聚焦一律暫停
const RUNNING_POLLING_INTERVAL_MS = 5_000

interface SummaryItemProps {
  label: string
  children: React.ReactNode
}

function SummaryItem({ label, children }: SummaryItemProps): React.ReactNode {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-sm font-medium text-muted-foreground md:text-base">
        {label}
      </dt>
      <dd className="text-sm text-foreground md:text-base">{children}</dd>
    </div>
  )
}

export default function RunDetailPage(): React.ReactNode {
  const { uid } = useParams<{ uid: string }>()
  // pollingInterval 需在拿到 data.status 前就決定,故用「render 期間依差異更新 state」
  // (React 官方認可的模式,非 useEffect)讓輪詢間隔在下一輪 render 就反映最新 status
  const [pollingMs, setPollingMs] = useState(0)
  const [prevIsRunning, setPrevIsRunning] = useState<boolean | null>(null)
  const { data, isLoading, isError, error, isFetching, refetch } =
    useGetRunQuery(uid, {
      pollingInterval: pollingMs,
      skipPollingIfUnfocused: true,
    })
  const lastUpdatedAt = useLastUpdatedAt(isFetching)
  const isRunning = data?.status === 'running'

  // run 結束(non-running)即停輪詢;首次拿到 status 前預設不輪詢
  if (isRunning !== prevIsRunning) {
    setPrevIsRunning(isRunning)
    setPollingMs(isRunning ? RUNNING_POLLING_INTERVAL_MS : 0)
  }

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <Link
          href="/runs"
          className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline md:text-base"
        >
          ← 回執行紀錄清單
        </Link>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {extractApiErrorDetail(error, '載入執行詳細資訊失敗,請稍後再試')}
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div className="df-card flex flex-col gap-4 p-5 md:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-xl font-bold text-foreground md:text-2xl">
                  執行詳細資訊
                </h1>
                <StatusBadge status={data.status} />
              </div>
              <AutoRefreshControl
                onRefresh={refetch}
                isFetching={isFetching}
                lastUpdatedAt={lastUpdatedAt}
                polling={isRunning}
                intervalSeconds={RUNNING_POLLING_INTERVAL_MS / 1000}
              />
            </div>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <SummaryItem label="觸發方式">
                {TRIGGER_TYPE_LABELS[data.trigger_type] ?? data.trigger_type}
              </SummaryItem>
              <SummaryItem label="開始時間">
                {formatNullableDateTime(data.started_at)}
              </SummaryItem>
              <SummaryItem label="結束時間">
                {formatNullableDateTime(data.finished_at)}
              </SummaryItem>
              <SummaryItem label="總表數">{data.total_tables}</SummaryItem>
              <SummaryItem label="成功表數">
                <span className="text-success">{data.success_tables}</span>
              </SummaryItem>
              <SummaryItem label="失敗表數">
                <span
                  className={data.failed_tables > 0 ? 'text-danger' : undefined}
                >
                  {data.failed_tables}
                </span>
              </SummaryItem>
              <SummaryItem label="建立時間">
                {formatDateTime(data.created_at)}
              </SummaryItem>
            </dl>
            {data.error_message !== null && data.error_message !== '' ? (
              <p
                role="alert"
                className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
              >
                {data.error_message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-3">
            <h2 className="text-lg font-bold text-foreground md:text-xl">
              逐表詳細 log
            </h2>
            <RunLogTable runUid={uid} isRunning={isRunning} />
          </div>
        </>
      ) : null}
    </section>
  )
}
