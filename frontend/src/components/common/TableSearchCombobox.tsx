'use client'

import { useCallback, useEffect, useId, useMemo, useState } from 'react'

/** 建議項:業務名稱 + 資料表名稱 */
export interface SuggestItem {
  name: string
  business_name: string | null
}

/** 建議顯示字樣:業務名稱(資料表);無業務名則僅資料表 */
export function suggestLabel(item: SuggestItem): string {
  return item.business_name !== null && item.business_name !== ''
    ? `${item.business_name}（${item.name}）`
    : item.name
}

/**
 * 資料表搜尋 combobox:輸入業務名稱 / 資料表名稱,自訂下拉建議,可輸入任一名稱;
 * 本地 debounce 300ms 後才 onCommit(避免逐字打 API)。原始資料管理與排程管理共用。
 */
export function TableSearchCombobox({
  value,
  suggestions,
  onCommit,
}: {
  value: string
  suggestions: readonly SuggestItem[]
  onCommit: (value: string) => void
}): React.ReactNode {
  const listboxId = useId()
  const [text, setText] = useState(value)
  const [prevValue, setPrevValue] = useState(value)
  const [open, setOpen] = useState(false)
  // 外部清除篩選(keyword→'')時,於 render 期間清空本地輸入(不干擾選取後顯示的建議字樣)
  if (value !== prevValue) {
    setPrevValue(value)
    if (value === '') setText('')
  }
  // 停止輸入 300ms 後才送出,避免逐字打 API
  useEffect(() => {
    if (text.trim() === value) return
    const timer = setTimeout(() => onCommit(text.trim()), 300)
    return () => clearTimeout(timer)
  }, [text, value, onCommit])

  const query = text.trim().toLowerCase()
  const filtered = useMemo((): SuggestItem[] => {
    const matched =
      query === ''
        ? suggestions
        : suggestions.filter(
            (it) =>
              it.name.toLowerCase().includes(query) ||
              (it.business_name?.toLowerCase().includes(query) ?? false),
          )
    return matched.slice(0, 20)
  }, [suggestions, query])

  const handleSelect = useCallback(
    (item: SuggestItem): void => {
      setText(suggestLabel(item))
      onCommit(item.name)
      setOpen(false)
    },
    [onCommit],
  )

  return (
    <div className="relative w-full sm:w-96">
      <input
        type="search"
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="輸入業務名稱或資料表名稱搜尋"
        aria-label="業務名稱 / 資料表名稱搜尋"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        className="df-input w-full"
      />
      {open && filtered.length > 0 ? (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-border bg-card py-1 shadow-lg"
        >
          {filtered.map((item) => (
            <li key={item.name}>
              <button
                type="button"
                // onMouseDown 搶在 input blur 前觸發選取
                onMouseDown={(e) => {
                  e.preventDefault()
                  handleSelect(item)
                }}
                className="flex w-full flex-wrap items-center gap-x-2 px-3 py-2 text-left text-sm hover:bg-muted md:text-base"
              >
                {item.business_name !== null && item.business_name !== '' ? (
                  <>
                    <span className="text-foreground">{item.business_name}</span>
                    <span className="font-mono text-muted-foreground">
                      （{item.name}）
                    </span>
                  </>
                ) : (
                  <span className="font-mono text-foreground">{item.name}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
