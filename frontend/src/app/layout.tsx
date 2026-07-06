import type { Metadata } from 'next'
import { StoreProvider } from '@/store/provider'
import { ThemeManager } from '@/components/layout/ThemeManager'
import './globals.css'

export const metadata: Metadata = {
  title: 'ETL 管理後台',
  description: 'Data Center ETL 管理後台',
}

// 首屏前套用主題,避免淺 / 深色閃爍(FOUC);與 ThemeManager 的還原邏輯一致
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('data-center-etl-theme');if(!t){t=(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';}var h=document.documentElement;h.classList.toggle('dark',t==='dark');if(t==='light'||t==='dark'){h.removeAttribute('data-theme');}else{h.setAttribute('data-theme',t);}}catch(e){}})();`

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-TW" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <StoreProvider>
          <ThemeManager />
          {children}
        </StoreProvider>
      </body>
    </html>
  )
}
