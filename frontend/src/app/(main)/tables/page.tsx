'use client'

import { useCallback, useState } from 'react'
import { useListEtlTablesQuery } from '@/lib/api/etlConfigApi'
import { useAuth } from '@/lib/auth/useAuth'
import { TableList } from '@/components/tables/TableList'

const PAGE_SIZE = 20

export default function TablesPage(): React.ReactNode {
  const { isAdmin } = useAuth()
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = useListEtlTablesQuery({
    page,
    pageSize: PAGE_SIZE,
  })

  const handlePageChange = useCallback((nextPage: number): void => {
    setPage(nextPage)
  }, [])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900 md:text-2xl">
          資料表管理
        </h1>
        <p className="mt-1 text-sm text-gray-600 md:text-base">
          ETL 納管表清單:啟用 / 停用、欄位 mapping 與 Comment
        </p>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-500 md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 md:text-base"
        >
          載入資料表清單失敗,請稍後再試
        </p>
      ) : null}

      {data !== undefined ? (
        <TableList data={data} canEdit={isAdmin} onPageChange={handlePageChange} />
      ) : null}
    </section>
  )
}
