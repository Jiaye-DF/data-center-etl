'use client'

import { DatasetBrowser } from '@/components/datasets/DatasetBrowser'

export default function RawDataPage(): React.ReactNode {
  return (
    <DatasetBrowser
      dataset="source"
      title="原始資料管理"
      description="檢視從 ERP 系統同步進來的原始資料,可依資料分類查看每張資料表的筆數與最新同步時間"
    />
  )
}
