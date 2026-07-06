// 佈景主題資料:光影系列五款,id 對應 globals.css 的 .dark / [data-theme] 切換

export const THEME_STORAGE_KEY = 'data-center-etl-theme'

export type ThemeId = 'light' | 'dark' | 'cool' | 'warm' | 'purple'

export interface ThemeItem {
  id: ThemeId
  labelZh: string
  labelEn: string
  icon: string
  /** 縮圖預覽用色(background / foreground / primary / accent) */
  preview: {
    background: string
    foreground: string
    primary: string
    accent: string
  }
}

export const THEMES: ThemeItem[] = [
  {
    id: 'light',
    labelZh: '晨曦',
    labelEn: 'Dawn',
    icon: '◐',
    preview: {
      background: '#f8fafc',
      foreground: '#0f172a',
      primary: '#2563eb',
      accent: '#3b82f6',
    },
  },
  {
    id: 'cool',
    labelZh: '霧境',
    labelEn: 'Nordic',
    icon: '❅',
    preview: {
      background: '#f0f4f8',
      foreground: '#1e293b',
      primary: '#0ea5e9',
      accent: '#06b6d4',
    },
  },
  {
    id: 'warm',
    labelZh: '夕映',
    labelEn: 'Ember',
    icon: '◉',
    preview: {
      background: '#fdf6ec',
      foreground: '#44403c',
      primary: '#ea580c',
      accent: '#f59e0b',
    },
  },
  {
    id: 'purple',
    labelZh: '暮霞',
    labelEn: 'Twilight',
    icon: '✦',
    preview: {
      background: '#faf5ff',
      foreground: '#3b0764',
      primary: '#a855f7',
      accent: '#e879f9',
    },
  },
  {
    id: 'dark',
    labelZh: '深夜',
    labelEn: 'Midnight',
    icon: '☾',
    preview: {
      background: '#09090b',
      foreground: '#f4f4f5',
      primary: '#60a5fa',
      accent: '#93c5fd',
    },
  },
]

export const ALL_THEME_IDS: ThemeId[] = THEMES.map((t) => t.id)

export function isValidThemeId(value: string): value is ThemeId {
  return (ALL_THEME_IDS as string[]).includes(value)
}

/** 將主題套用到 <html>:dark 切 class,其餘非預設主題切 data-theme */
export function applyThemeToDocument(id: ThemeId): void {
  if (typeof document === 'undefined') {
    return
  }
  const html = document.documentElement
  html.classList.toggle('dark', id === 'dark')
  if (id === 'light' || id === 'dark') {
    html.removeAttribute('data-theme')
  } else {
    html.setAttribute('data-theme', id)
  }
}
