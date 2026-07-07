'use client'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
}

/** 通用膠囊篩選(pill;原始資料 / 排程 / 執行紀錄等頁共用同一視覺語言) */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: ReadonlyArray<SegmentedOption<T>>
  value: T
  onChange: (value: T) => void
}): React.ReactNode {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            aria-pressed={active}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors md:text-base ${
              active
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border bg-card text-foreground hover:bg-muted'
            }`}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
