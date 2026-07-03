'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useGetRunQuery } from '@/lib/api/runApi'
import { extractApiErrorDetail } from '@/lib/api/etlConfigApi'
import { formatDateTime } from '@/utils/datetime'
import {
  formatNullableDateTime,
  RunLogTable,
  StatusBadge,
  TRIGGER_TYPE_LABELS,
} from '@/components/runs/RunLogTable'

interface SummaryItemProps {
  label: string
  children: React.ReactNode
}

function SummaryItem({ label, children }: SummaryItemProps): React.ReactNode {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-sm font-medium text-gray-500 md:text-base">
        {label}
      </dt>
      <dd className="text-sm text-gray-900 md:text-base">{children}</dd>
    </div>
  )
}

export default function RunDetailPage(): React.ReactNode {
  const { uid } = useParams<{ uid: string }>()
  const { data, isLoading, isError, error } = useGetRunQuery(uid)

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <Link
          href="/runs"
          className="text-sm text-gray-600 underline-offset-2 hover:underline md:text-base"
        >
          ← 回執行紀錄清單
        </Link>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-500 md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 md:text-base"
        >
          {extractApiErrorDetail(error, '載入執行明細失敗,請稍後再試')}
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div className="flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm md:p-5">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-xl font-bold text-gray-900 md:text-2xl">
                執行明細
              </h1>
              <StatusBadge status={data.status} />
            </div>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <SummaryItem label="觸發方式">
                {TRIGGER_TYPE_LABELS[data.trigger_type] ?? data.trigger_type}
              </SummaryItem>
              <SummaryItem label="排程名稱">
                {data.schedule_name ?? '—'}
              </SummaryItem>
              <SummaryItem label="開始時間">
                {formatNullableDateTime(data.started_at)}
              </SummaryItem>
              <SummaryItem label="結束時間">
                {formatNullableDateTime(data.finished_at)}
              </SummaryItem>
              <SummaryItem label="總表數">{data.total_tables}</SummaryItem>
              <SummaryItem label="成功表數">
                <span className="text-green-700">{data.success_tables}</span>
              </SummaryItem>
              <SummaryItem label="失敗表數">
                <span
                  className={data.failed_tables > 0 ? 'text-red-700' : undefined}
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
                className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 md:text-base"
              >
                {data.error_message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-3">
            <h2 className="text-lg font-bold text-gray-900 md:text-xl">
              逐表詳細 log
            </h2>
            <RunLogTable runUid={uid} />
          </div>
        </>
      ) : null}
    </section>
  )
}
