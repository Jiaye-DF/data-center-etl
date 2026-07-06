'use client'

import { DatasetBrowser } from '@/components/datasets/DatasetBrowser'

export default function RawDataPage(): React.ReactNode {
  return (
    <DatasetBrowser
      dataset="source"
      title="原始資料管理"
      description="來源 ERP 原始資料庫(Raw Data):依 schema 瀏覽資料表與欄位結構"
    />
  )
}
