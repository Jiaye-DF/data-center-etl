'use client'

import { DatasetBrowser } from '@/components/datasets/DatasetBrowser'

export default function EtlDataPage(): React.ReactNode {
  return (
    <DatasetBrowser
      dataset="target"
      title="ETL 資料管理"
      description="ETL 轉換後的資料中心庫:依 schema 瀏覽已同步 / 轉換的資料表快照"
    />
  )
}
