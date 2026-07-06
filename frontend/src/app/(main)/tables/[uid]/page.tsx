'use client'

import { useCallback, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import {
  useGetEtlTableQuery,
  useSetEtlTableEnabledMutation,
} from '@/lib/api/etlConfigApi'
import { extractApiErrorDetail } from '@/utils/apiError'
import { useAuth } from '@/lib/auth/useAuth'
import { MappingEditor } from '@/components/tables/MappingEditor'

export default function TableDetailPage(): React.ReactNode {
  const { uid } = useParams<{ uid: string }>()
  const { isAdmin } = useAuth()
  const { data, isLoading, isError, error } = useGetEtlTableQuery(uid)
  const [setEnabled, { isLoading: isToggling }] =
    useSetEtlTableEnabledMutation()
  const [toggleError, setToggleError] = useState<string | null>(null)

  const handleToggle = useCallback(async (): Promise<void> => {
    if (data === undefined) {
      return
    }
    setToggleError(null)
    const result = await setEnabled({ uid, enabled: !data.is_enabled })
    if ('error' in result) {
      setToggleError(
        extractApiErrorDetail(result.error, '切換啟用狀態失敗,請稍後再試'),
      )
    }
  }, [setEnabled, uid, data])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <Link
          href="/tables"
          className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline md:text-base"
        >
          ← 回資料表清單
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
          {extractApiErrorDetail(error, '載入資料表明細失敗,請稍後再試')}
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div className="df-card flex flex-col gap-3 p-5 md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-xl font-bold text-foreground md:text-2xl">
                  {data.source_schema}.{data.source_table}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground md:text-base">
                  目標:{data.target_schema}.{data.target_table}
                </p>
                {data.description !== null && data.description !== '' ? (
                  <p className="mt-1 text-sm text-muted-foreground md:text-base">
                    {data.description}
                  </p>
                ) : null}
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`df-badge ${
                    data.is_enabled
                      ? 'bg-success/15 text-success'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {data.is_enabled ? '啟用中' : '已停用'}
                </span>
                {isAdmin ? (
                  <button
                    type="button"
                    onClick={handleToggle}
                    disabled={isToggling}
                    className="df-btn-warning-soft"
                  >
                    {isToggling
                      ? '切換中…'
                      : data.is_enabled
                        ? '停用此表'
                        : '啟用此表'}
                  </button>
                ) : null}
              </div>
            </div>
            {toggleError !== null ? (
              <p
                role="alert"
                className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
              >
                {toggleError}
              </p>
            ) : null}
          </div>

          <MappingEditor
            tableUid={uid}
            mappings={data.mappings}
            readOnly={!isAdmin}
          />
        </>
      ) : null}
    </section>
  )
}
