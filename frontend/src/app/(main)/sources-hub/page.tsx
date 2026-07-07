'use client'

import { DatasetBrowser } from '@/components/datasets/DatasetBrowser'

export default function SourcesHubPage(): React.ReactNode {
  return (
    <DatasetBrowser
      dataset="target"
      title="ETL 資料管理"
      description="檢視經 ETL 轉換後存入資料中心的資料,可依資料分類查看每張資料表的筆數與最新轉換時間"
    />
  )
}
