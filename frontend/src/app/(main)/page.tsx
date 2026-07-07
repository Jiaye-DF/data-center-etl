'use client'

import { memo, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth/useAuth'
import { consumeReauthReturnTo } from '@/lib/auth/sso'
import {
  useDashboardOverviewQuery,
  type DashboardDatasetScale,
  type DashboardFailedTable,
  type DashboardLatestRun,
} from '@/lib/api/dashboardApi'
import { StatusBadge } from '@/components/common/StatusBadge'
import { formatNullableDateTime } from '@/utils/datetime'
import { nextRunFromCron } from '@/utils/cron'

interface SectionItem {
  href: string
  title: string
  description: string
}

const SECTIONS: SectionItem[] = [
  {
    href: '/sources',
    title: '原始資料管理',
    description: '瀏覽來源 ERP 原始資料庫的 schema 與資料表結構',
  },
  {
    href: '/sources-hub',
    title: 'ETL 資料管理',
    description: '瀏覽 ETL 轉換後的資料中心庫',
  },
  {
    href: '/schedules',
    title: '排程管理',
    description: '排程設定與手動觸發',
  },
  {
    href: '/runs',
    title: '執行紀錄',
    description: '執行紀錄與逐表詳細 log',
  },
]

const DATASET_LABELS: Record<string, string> = {
  source: '原始資料',
  target: 'ETL 資料',
}

function pad2(value: number): string {
  return value.toString().padStart(2, '0')
}

/** Date → YYYY/MM/DD HH:mm(使用者本地時間;UTC+8 語意由後端 cron 定義) */
function formatDate(date: Date): string {
  return `${date.getFullYear()}/${pad2(date.getMonth() + 1)}/${pad2(
    date.getDate(),
  )} ${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

/** 卡片外殼:標題列 + 內容 */
function Panel({
  title,
  action,
  children,
}: {
  title: string
  action?: React.ReactNode
  children: React.ReactNode
}): React.ReactNode {
  return (
    <div className="df-card flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground md:text-base">
          <span aria-hidden className="h-4 w-1 rounded-full bg-primary" />
          {title}
        </span>
        {action}
      </div>
      {children}
    </div>
  )
}

/** 數值格:小標 + 數字 */
function Stat({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: string
  tone?: 'default' | 'success' | 'danger' | 'muted'
}): React.ReactNode {
  const toneClass =
    tone === 'success'
      ? 'text-success'
      : tone === 'danger'
        ? 'text-danger'
        : tone === 'muted'
          ? 'text-muted-foreground'
          : 'text-foreground'
  return (
    <div className="flex min-w-[72px] flex-col gap-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-lg font-semibold md:text-xl ${toneClass}`}>
        {value}
      </span>
    </div>
  )
}

/** 同步健康 */
function SyncHealthPanel({
  latestRun,
  recentTotal,
  recentSuccess,
  recentFailed,
}: {
  latestRun: DashboardLatestRun | null
  recentTotal: number
  recentSuccess: number
  recentFailed: number
}): React.ReactNode {
  return (
    <Panel
      title="同步健康"
      action={
        <Link href="/runs" className="text-sm text-primary hover:underline">
          執行紀錄 →
        </Link>
      }
    >
      {latestRun === null ? (
        <p className="text-sm text-muted-foreground md:text-base">尚無執行紀錄</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="text-sm text-muted-foreground">最近一次</span>
            <StatusBadge status={latestRun.status} />
            <span className="text-sm text-muted-foreground">
              {latestRun.trigger_type === 'schedule' ? '排程' : '手動'} ·{' '}
              {formatNullableDateTime(latestRun.finished_at)}
            </span>
          </div>
          <div className="flex flex-wrap gap-6">
            <Stat label="涵蓋表" value={latestRun.total_tables.toLocaleString()} />
            <Stat
              label="成功"
              value={latestRun.success_tables.toLocaleString()}
              tone="success"
            />
            <Stat
              label="失敗"
              value={latestRun.failed_tables.toLocaleString()}
              tone={latestRun.failed_tables > 0 ? 'danger' : 'muted'}
            />
            <Stat
              label={`近 ${recentTotal} 次成功`}
              value={
                recentTotal === 0
                  ? '—'
                  : `${recentSuccess}/${recentTotal}`
              }
              tone={recentFailed > 0 ? 'danger' : 'success'}
            />
          </div>
        </div>
      )}
    </Panel>
  )
}

/** ETL 同步失敗資料表 */
function PendingFailuresPanel({
  runUid,
  items,
}: {
  runUid: string | null
  items: DashboardFailedTable[]
}): React.ReactNode {
  return (
    <Panel
      title="ETL 同步失敗資料表"
      action={
        runUid !== null ? (
          <Link
            href={`/runs/${runUid}`}
            className="text-sm text-primary hover:underline"
          >
            查看該次執行 →
          </Link>
        ) : undefined
      }
    >
      {items.length === 0 ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success md:text-base">
          目前無同步失敗
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {items.map((item) => (
            <li
              key={`${item.source_schema}.${item.source_table}`}
              className="flex flex-col gap-0.5 py-2"
            >
              <span className="font-mono text-sm font-medium text-foreground md:text-base">
                {item.source_schema}.{item.source_table}
              </span>
              {item.error_message !== null ? (
                <span className="truncate text-sm text-danger">
                  {item.error_message}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

/** 資料規模 + 快照新鮮度 */
function DatasetScaleCard({
  scale,
}: {
  scale: DashboardDatasetScale
}): React.ReactNode {
  return (
    <div className="df-card flex flex-col gap-3 p-4">
      <span className="text-sm font-semibold text-foreground md:text-base">
        {DATASET_LABELS[scale.dataset] ?? scale.dataset}
      </span>
      <div className="flex flex-wrap gap-5">
        <Stat label="總表數" value={scale.table_count.toLocaleString()} />
        <Stat label="有資料" value={scale.nonempty_count.toLocaleString()} />
        <Stat
          label="空表"
          value={scale.empty_count.toLocaleString()}
          tone="muted"
        />
      </div>
      <div className="flex flex-col gap-0.5 text-sm text-muted-foreground">
        <span>快照:{formatNullableDateTime(scale.last_snapshot_at)}</span>
        <span>同步:{formatNullableDateTime(scale.last_synced_at)}</span>
      </div>
    </div>
  )
}

interface SectionCardProps {
  item: SectionItem
}

const SectionCard = memo(function SectionCard({
  item,
}: SectionCardProps): React.ReactNode {
  return (
    <Link
      href={item.href}
      className="df-card group flex min-h-[44px] flex-col gap-1.5 p-5 transition-all hover:-translate-y-0.5 hover:border-primary hover:shadow-md"
    >
      <span className="flex items-center gap-2 text-base font-semibold text-foreground md:text-lg">
        {item.title}
        <span className="text-muted-foreground transition-transform group-hover:translate-x-0.5">
          →
        </span>
      </span>
      <span className="text-sm text-muted-foreground md:text-base">
        {item.description}
      </span>
    </Link>
  )
})

export default function DashboardPage(): React.ReactNode {
  const router = useRouter()
  const { user } = useAuth()
  const { data, isLoading, isError } = useDashboardOverviewQuery()

  // silent re-auth 保留現場復原:登入成功回到 dashboard 時導回原頁(復原一次即清除)
  useEffect(() => {
    const returnTo = consumeReauthReturnTo()
    if (returnTo !== null && returnTo !== '/') {
      router.replace(returnTo)
    }
  }, [router])

  const nextRun = useMemo((): Date | null => {
    const times = (data?.schedules.enabled_cron_exprs ?? [])
      .map((cron) => nextRunFromCron(cron))
      .filter((d): d is Date => d !== null)
      .map((d) => d.getTime())
    return times.length > 0 ? new Date(Math.min(...times)) : null
  }, [data])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-foreground md:text-2xl">總覽</h1>
        {user !== null ? (
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            歡迎,{user.username}
          </p>
        ) : null}
      </div>

      {isError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入總覽資料失敗,請稍後再試
        </p>
      ) : null}
      {isLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}

      {data !== undefined ? (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SyncHealthPanel
              latestRun={data.sync_health.latest_run}
              recentTotal={data.sync_health.recent_total}
              recentSuccess={data.sync_health.recent_success}
              recentFailed={data.sync_health.recent_failed}
            />
            <PendingFailuresPanel
              runUid={data.pending_failures.run_uid}
              items={data.pending_failures.items}
            />
          </div>

          <Panel
            title="下一班排程"
            action={
              <Link
                href="/schedules"
                className="text-sm text-primary hover:underline"
              >
                排程管理 →
              </Link>
            }
          >
            <div className="flex flex-wrap gap-6">
              <Stat
                label="下次執行"
                value={nextRun === null ? '無啟用排程' : formatDate(nextRun)}
                tone={nextRun === null ? 'muted' : 'default'}
              />
              <Stat
                label="啟用中排程"
                value={`${data.schedules.enabled_count}/${data.schedules.table_total}`}
              />
            </div>
          </Panel>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {data.datasets.map((scale) => (
              <DatasetScaleCard key={scale.dataset} scale={scale} />
            ))}
          </div>
        </>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {SECTIONS.map((item) => (
          <SectionCard key={item.href} item={item} />
        ))}
      </div>
    </section>
  )
}
