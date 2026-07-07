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
 *
 * onCommit 第二參數 exact:自下拉選定某表為 true(關鍵字為該表名,後端精準等值,
 * 不會被子字串誤命中他表);自由打字為 false(後端對表名 / 業務名子字串模糊比對)。
 */
export function TableSearchCombobox({
  value,
  suggestions,
  onCommit,
}: {
  value: string
  suggestions: readonly SuggestItem[]
  onCommit: (value: string, exact: boolean) => void
}): React.ReactNode {
  const listboxId = useId()
  const [text, setText] = useState(value)
  // 上次提交(打字送出 / 選取建議)當下的顯示文字;選取建議時顯示為 label 但關鍵字為 name,
  // 故不能拿顯示文字直接比對外部 value,否則會把 label 誤當新輸入再次覆寫關鍵字
  const [settledText, setSettledText] = useState(value)
  const [prevValue, setPrevValue] = useState(value)
  const [open, setOpen] = useState(false)
  // 外部清除篩選(keyword→'')時,於 render 期間清空本地輸入(不干擾選取後顯示的建議字樣)
  if (value !== prevValue) {
    setPrevValue(value)
    if (value === '') {
      setText('')
      setSettledText('')
    }
  }
  // 停止輸入 300ms 後才送出,避免逐字打 API
  useEffect(() => {
    if (text.trim() === settledText.trim()) return
    const timer = setTimeout(() => {
      // 自由打字 → 模糊比對(exact=false)
      onCommit(text.trim(), false)
      setSettledText(text)
    }, 300)
    return () => clearTimeout(timer)
  }, [text, settledText, onCommit])

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
      const label = suggestLabel(item)
      setText(label)
      setSettledText(label)
      // 選定某表 → 精準等值(exact=true),只命中該表
      onCommit(item.name, true)
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
