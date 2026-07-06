'use client'

import { memo, useCallback, useMemo } from 'react'

export interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export const Pagination = memo(function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: PaginationProps): React.ReactNode {
  const totalPages = useMemo(
    (): number => Math.max(1, Math.ceil(total / pageSize)),
    [total, pageSize],
  )

  const handlePrev = useCallback((): void => {
    onPageChange(page - 1)
  }, [onPageChange, page])

  const handleNext = useCallback((): void => {
    onPageChange(page + 1)
  }, [onPageChange, page])

  return (
    <div className="flex items-center justify-between gap-2">
      <p className="text-sm text-gray-600 md:text-base">
        共 {total} 筆,第 {page} / {totalPages} 頁
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={handlePrev}
          disabled={page <= 1}
          className="min-h-[44px] rounded border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 md:text-base"
        >
          上一頁
        </button>
        <button
          type="button"
          onClick={handleNext}
          disabled={page >= totalPages}
          className="min-h-[44px] rounded border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 md:text-base"
        >
          下一頁
        </button>
      </div>
    </div>
  )
})
