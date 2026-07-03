'use client'

import { memo, useCallback, useMemo, useState } from 'react'
import {
  extractApiErrorDetail,
  useReplaceEtlTableMappingsMutation,
  type EtlMapping,
  type EtlMappingUpsert,
} from '@/lib/api/etlConfigApi'

/** 編輯中的 mapping 草稿列(key 供 React 列表重排使用,與後端 uid 解耦) */
interface DraftRow {
  key: string
  source_column: string
  target_column: string
  transform_type: string
  comment: string
}

/** 可編輯欄位名(row 內更新用) */
type DraftField = 'source_column' | 'target_column' | 'transform_type' | 'comment'

let nextDraftKey = 0

function newDraftKey(): string {
  nextDraftKey += 1
  return `draft-${nextDraftKey}`
}

function toDraftRows(mappings: EtlMapping[]): DraftRow[] {
  return [...mappings]
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((m) => ({
      key: newDraftKey(),
      source_column: m.source_column,
      target_column: m.target_column,
      transform_type: m.transform_type ?? '',
      comment: m.comment,
    }))
}

interface MappingRowProps {
  row: DraftRow
  index: number
  readOnly: boolean
  onFieldChange: (key: string, field: DraftField, value: string) => void
  onRemove: (key: string) => void
}

const DRAFT_FIELDS: readonly DraftField[] = [
  'source_column',
  'target_column',
  'transform_type',
  'comment',
]

function isDraftField(value: string): value is DraftField {
  return (DRAFT_FIELDS as readonly string[]).includes(value)
}

const MappingRow = memo(function MappingRow({
  row,
  index,
  readOnly,
  onFieldChange,
  onRemove,
}: MappingRowProps): React.ReactNode {
  // 單一 handler + input name 辨識欄位,避免 render 期建立多個新函式 props
  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      const field = event.target.name
      if (isDraftField(field)) {
        onFieldChange(row.key, field, event.target.value)
      }
    },
    [onFieldChange, row.key],
  )

  const handleRemove = useCallback((): void => {
    onRemove(row.key)
  }, [onRemove, row.key])

  // 缺 Comment 欄位醒目標示(後端每欄位必帶 Comment,缺值儲存會 400)
  const commentMissing = row.comment.trim() === ''
  const inputClass =
    'min-h-[44px] w-full rounded border px-2 text-sm text-gray-900 disabled:bg-gray-50 disabled:text-gray-500 md:min-h-[36px] md:text-base'

  return (
    <tr className="border-b border-gray-100 align-top last:border-b-0">
      <td className="px-2 py-2 text-sm text-gray-500 md:text-base">
        {index + 1}
      </td>
      <td className="px-2 py-2">
        <input
          type="text"
          name="source_column"
          value={row.source_column}
          onChange={handleChange}
          disabled={readOnly}
          aria-label="來源欄位"
          className={`${inputClass} border-gray-300`}
        />
      </td>
      <td className="px-2 py-2">
        <input
          type="text"
          name="target_column"
          value={row.target_column}
          onChange={handleChange}
          disabled={readOnly}
          aria-label="目標欄位"
          className={`${inputClass} border-gray-300`}
        />
      </td>
      <td className="px-2 py-2">
        <input
          type="text"
          name="transform_type"
          value={row.transform_type}
          onChange={handleChange}
          disabled={readOnly}
          aria-label="轉換型別"
          placeholder="(無)"
          className={`${inputClass} border-gray-300`}
        />
      </td>
      <td className="px-2 py-2">
        <input
          type="text"
          name="comment"
          value={row.comment}
          onChange={handleChange}
          disabled={readOnly}
          aria-label="欄位 Comment"
          className={`${inputClass} ${commentMissing ? 'border-red-400 bg-red-50' : 'border-gray-300'}`}
        />
        {commentMissing ? (
          <p className="mt-1 text-sm text-red-600">缺 Comment(必填)</p>
        ) : null}
      </td>
      {!readOnly ? (
        <td className="px-2 py-2">
          <button
            type="button"
            onClick={handleRemove}
            className="min-h-[44px] min-w-[44px] rounded border border-gray-300 px-2 text-sm font-medium text-gray-700 hover:bg-gray-100 md:min-h-[36px] md:min-w-0 md:text-base"
          >
            刪除
          </button>
        </td>
      ) : null}
    </tr>
  )
})

export interface MappingEditorProps {
  tableUid: string
  mappings: EtlMapping[]
  /** viewer 角色為 true:輸入框 disabled、新增 / 刪除 / 儲存隱藏 */
  readOnly: boolean
}

export function MappingEditor({
  tableUid,
  mappings,
  readOnly,
}: MappingEditorProps): React.ReactNode {
  const [rows, setRows] = useState<DraftRow[]>(() => toDraftRows(mappings))
  const [prevMappings, setPrevMappings] = useState<EtlMapping[]>(mappings)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)
  const [replaceMappings, { isLoading: isSaving }] =
    useReplaceEtlTableMappingsMutation()

  // 後端資料更新(儲存成功 refetch / 切換啟停)→ 以伺服器版本重置草稿
  // (render 期調整 state 的官方模式,避免 effect 內 setState 造成級聯 render)
  if (prevMappings !== mappings) {
    setPrevMappings(mappings)
    setRows(toDraftRows(mappings))
  }

  const handleFieldChange = useCallback(
    (key: string, field: DraftField, value: string): void => {
      setSavedMessage(null)
      setRows((prev) =>
        prev.map((row) => (row.key === key ? { ...row, [field]: value } : row)),
      )
    },
    [],
  )

  const handleRemove = useCallback((key: string): void => {
    setSavedMessage(null)
    setRows((prev) => prev.filter((row) => row.key !== key))
  }, [])

  const handleAdd = useCallback((): void => {
    setSavedMessage(null)
    setRows((prev) => [
      ...prev,
      {
        key: newDraftKey(),
        source_column: '',
        target_column: '',
        transform_type: '',
        comment: '',
      },
    ])
  }, [])

  const missingCommentCount = useMemo(
    (): number => rows.filter((row) => row.comment.trim() === '').length,
    [rows],
  )

  const handleSave = useCallback(async (): Promise<void> => {
    setErrorMessage(null)
    setSavedMessage(null)
    const payload: EtlMappingUpsert[] = rows.map((row, index) => ({
      source_column: row.source_column.trim(),
      target_column: row.target_column.trim(),
      transform_type:
        row.transform_type.trim() === '' ? null : row.transform_type.trim(),
      comment: row.comment.trim() === '' ? null : row.comment.trim(),
      sort_order: index,
    }))
    const result = await replaceMappings({ uid: tableUid, mappings: payload })
    if ('error' in result) {
      // 400(缺 Comment / 重複欄位等)顯示後端訊息
      setErrorMessage(
        extractApiErrorDetail(result.error, '儲存 mapping 失敗,請稍後再試'),
      )
      return
    }
    setSavedMessage('mapping 已儲存')
  }, [replaceMappings, tableUid, rows])

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-gray-900 md:text-xl">
          欄位 mapping(共 {rows.length} 欄
          {missingCommentCount > 0 ? `,${missingCommentCount} 欄缺 Comment` : ''})
        </h2>
        {!readOnly ? (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleAdd}
              className="min-h-[44px] rounded border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-100 md:text-base"
            >
              新增欄位
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving}
              className="min-h-[44px] rounded bg-gray-900 px-4 text-sm font-medium text-white disabled:opacity-50 md:text-base"
            >
              {isSaving ? '儲存中…' : '儲存 mapping'}
            </button>
          </div>
        ) : null}
      </div>

      {errorMessage !== null ? (
        <p
          role="alert"
          className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 md:text-base"
        >
          {errorMessage}
        </p>
      ) : null}
      {savedMessage !== null ? (
        <p className="rounded bg-green-50 px-3 py-2 text-sm text-green-700 md:text-base">
          {savedMessage}
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="w-full min-w-[720px] text-left">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="px-2 py-2 text-sm font-semibold text-gray-700 md:text-base">
                #
              </th>
              <th className="px-2 py-2 text-sm font-semibold text-gray-700 md:text-base">
                來源欄位
              </th>
              <th className="px-2 py-2 text-sm font-semibold text-gray-700 md:text-base">
                目標欄位
              </th>
              <th className="px-2 py-2 text-sm font-semibold text-gray-700 md:text-base">
                轉換型別
              </th>
              <th className="px-2 py-2 text-sm font-semibold text-gray-700 md:text-base">
                Comment
              </th>
              {!readOnly ? (
                <th className="px-2 py-2 text-sm font-semibold text-gray-700 md:text-base">
                  操作
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <MappingRow
                key={row.key}
                row={row}
                index={index}
                readOnly={readOnly}
                onFieldChange={handleFieldChange}
                onRemove={handleRemove}
              />
            ))}
          </tbody>
        </table>
        {rows.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-gray-500 md:text-base">
            尚無 mapping 欄位
          </p>
        ) : null}
      </div>
    </section>
  )
}
