'use client'

import { useCallback, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import {
  extractApiErrorDetail,
  useGetEtlTableQuery,
  useSetEtlTableEnabledMutation,
} from '@/lib/api/etlConfigApi'
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
          className="text-sm text-gray-600 underline-offset-2 hover:underline md:text-base"
        >
          ← 回資料表清單
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
          {extractApiErrorDetail(error, '載入資料表明細失敗,請稍後再試')}
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm md:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-xl font-bold text-gray-900 md:text-2xl">
                  {data.source_schema}.{data.source_table}
                </h1>
                <p className="mt-1 text-sm text-gray-600 md:text-base">
                  目標:{data.target_schema}.{data.target_table}
                </p>
                {data.description !== null && data.description !== '' ? (
                  <p className="mt-1 text-sm text-gray-500 md:text-base">
                    {data.description}
                  </p>
                ) : null}
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`rounded px-2 py-0.5 text-sm font-medium md:text-base ${
                    data.is_enabled
                      ? 'bg-green-50 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {data.is_enabled ? '啟用中' : '已停用'}
                </span>
                {isAdmin ? (
                  <button
                    type="button"
                    onClick={handleToggle}
                    disabled={isToggling}
                    className="min-h-[44px] rounded border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 md:text-base"
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
                className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 md:text-base"
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
