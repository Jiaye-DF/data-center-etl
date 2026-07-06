'use client'

import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import {
  useListDatasetColumnsQuery,
  useListDatasetSchemasQuery,
  useListDatasetTablesQuery,
  type Dataset,
  type TableSummary,
} from '@/lib/api/datasetApi'
import { Pagination } from '@/components/common/Pagination'

const PAGE_SIZE = 50

/** DS(資料字典)恆置最前,其餘 schema 依名稱排序 */
function orderSchemas(names: string[]): string[] {
  return [...names].sort((a, b) => {
    if (a === 'DS') return -1
    if (b === 'DS') return 1
    return a.localeCompare(b)
  })
}

function formatRowEstimate(value: number): string {
  return value < 0 ? '—' : `≈ ${value.toLocaleString()}`
}

interface DatasetBrowserProps {
  dataset: Dataset
  title: string
  description: string
}

export function DatasetBrowser({
  dataset,
  title,
  description,
}: DatasetBrowserProps): React.ReactNode {
  const {
    data: schemas,
    isLoading: schemasLoading,
    isError: schemasError,
  } = useListDatasetSchemasQuery(dataset)

  const [activeSchema, setActiveSchema] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const orderedSchemas = useMemo(
    () => orderSchemas((schemas ?? []).map((s) => s.schema)),
    [schemas],
  )

  // schemas 載入後預設選第一個(DS 優先)
  useEffect(() => {
    const first = orderedSchemas[0]
    if (activeSchema === null && first !== undefined) {
      setActiveSchema(first)
    }
  }, [activeSchema, orderedSchemas])

  const handleSchemaSelect = useCallback((schema: string): void => {
    setActiveSchema(schema)
    setPage(1)
  }, [])

  const handlePageChange = useCallback((next: number): void => {
    setPage(next)
  }, [])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-foreground md:text-2xl">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground md:text-base">
          {description}
        </p>
      </div>

      {schemasError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          無法連線到資料庫或讀取結構失敗,請確認 RDS 連線設定
        </p>
      ) : null}
      {schemasLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}

      {schemas !== undefined && schemas.length === 0 ? (
        <div className="df-card p-8 text-center text-sm text-muted-foreground md:text-base">
          此資料庫尚無任何 schema / 資料表
        </div>
      ) : null}

      {orderedSchemas.length > 0 ? (
        <>
          <div className="flex flex-wrap gap-2">
            {orderedSchemas.map((schema) => {
              const count =
                schemas?.find((s) => s.schema === schema)?.table_count ?? 0
              const active = schema === activeSchema
              return (
                <button
                  key={schema}
                  type="button"
                  onClick={() => handleSchemaSelect(schema)}
                  aria-pressed={active}
                  className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors md:text-base ${
                    active
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border bg-card text-foreground hover:bg-muted'
                  }`}
                >
                  {schema}
                  <span
                    className={`rounded-full px-2 py-0.5 text-sm ${active ? 'bg-white/20' : 'bg-muted text-muted-foreground'}`}
                  >
                    {count}
                  </span>
                </button>
              )
            })}
          </div>

          {activeSchema !== null ? (
            <SchemaTables
              dataset={dataset}
              schema={activeSchema}
              page={page}
              onPageChange={handlePageChange}
            />
          ) : null}
        </>
      ) : null}
    </section>
  )
}

interface SchemaTablesProps {
  dataset: Dataset
  schema: string
  page: number
  onPageChange: (page: number) => void
}

function SchemaTables({
  dataset,
  schema,
  page,
  onPageChange,
}: SchemaTablesProps): React.ReactNode {
  const { data, isLoading, isError, isFetching } = useListDatasetTablesQuery({
    dataset,
    schema,
    page,
    pageSize: PAGE_SIZE,
  })
  const [expanded, setExpanded] = useState<string | null>(null)

  const handleToggle = useCallback((name: string): void => {
    setExpanded((prev) => (prev === name ? null : name))
  }, [])

  if (isLoading) {
    return <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
  }
  if (isError || data === undefined) {
    return (
      <p
        role="alert"
        className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
      >
        載入 {schema} 的資料表失敗,請稍後再試
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className={`df-card overflow-x-auto transition-opacity ${isFetching ? 'opacity-60' : ''}`}
      >
        <table className="df-table min-w-[640px]">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="df-th">資料表</th>
              <th className="df-th">欄位數</th>
              <th className="df-th">資料筆數(估算)</th>
              <th className="df-th">欄位結構</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((table) => (
              <TableRow
                key={table.name}
                dataset={dataset}
                schema={schema}
                table={table}
                expanded={expanded === table.name}
                onToggle={handleToggle}
              />
            ))}
          </tbody>
        </table>
        {data.items.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
            此 schema 尚無資料表
          </p>
        ) : null}
      </div>
      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        onPageChange={onPageChange}
      />
    </div>
  )
}

interface TableRowProps {
  dataset: Dataset
  schema: string
  table: TableSummary
  expanded: boolean
  onToggle: (name: string) => void
}

const TableRow = memo(function TableRow({
  dataset,
  schema,
  table,
  expanded,
  onToggle,
}: TableRowProps): React.ReactNode {
  const handleToggle = useCallback((): void => {
    onToggle(table.name)
  }, [onToggle, table.name])

  return (
    <>
      <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
        <td className="px-3 py-3 font-mono text-sm font-medium text-foreground md:text-base">
          {table.name}
        </td>
        <td className="df-td text-muted-foreground">{table.column_count}</td>
        <td className="df-td text-muted-foreground">
          {formatRowEstimate(table.row_estimate)}
        </td>
        <td className="px-3 py-3">
          <button
            type="button"
            onClick={handleToggle}
            aria-expanded={expanded}
            className="df-btn-outline min-h-[36px] px-3"
          >
            {expanded ? '收合' : '查看欄位'}
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr className="border-b border-border bg-muted/30 last:border-b-0">
          <td colSpan={4} className="px-3 py-3">
            <ColumnsPanel dataset={dataset} schema={schema} table={table.name} />
          </td>
        </tr>
      ) : null}
    </>
  )
})

interface ColumnsPanelProps {
  dataset: Dataset
  schema: string
  table: string
}

function ColumnsPanel({
  dataset,
  schema,
  table,
}: ColumnsPanelProps): React.ReactNode {
  const { data, isLoading, isError } = useListDatasetColumnsQuery({
    dataset,
    schema,
    table,
  })

  if (isLoading) {
    return <p className="text-sm text-muted-foreground md:text-base">載入欄位…</p>
  }
  if (isError || data === undefined) {
    return (
      <p className="text-sm text-danger md:text-base">載入欄位結構失敗</p>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {data.map((col) => (
        <span
          key={col.name}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1 text-sm md:text-base"
        >
          <span className="font-mono font-medium text-foreground">
            {col.name}
          </span>
          <span className="text-muted-foreground">{col.data_type}</span>
          {col.nullable ? null : (
            <span className="rounded bg-warning/15 px-1.5 text-sm text-warning">
              NOT NULL
            </span>
          )}
        </span>
      ))}
    </div>
  )
}
