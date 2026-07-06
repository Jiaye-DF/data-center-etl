import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import { type ThemeId } from '@/lib/theme/themes'

export type SidebarState = 'expanded' | 'collapsed' | 'hidden'

interface ThemeState {
  theme: ThemeId
  /** 桌機側欄三態:展開 / 收合(僅圖示)/ 隱藏 */
  sidebarState: SidebarState
  /** 手機側欄抽屜開關(獨立於桌機三態) */
  mobileNavOpen: boolean
}

// 初值 light;實際偏好由 ThemeManager 掛載時自 localStorage / 系統偏好還原
const initialState: ThemeState = {
  theme: 'light',
  sidebarState: 'expanded',
  mobileNavOpen: false,
}

const CYCLE: Record<SidebarState, SidebarState> = {
  expanded: 'collapsed',
  collapsed: 'hidden',
  hidden: 'expanded',
}

const themeSlice = createSlice({
  name: 'theme',
  initialState,
  reducers: {
    setTheme(state, action: PayloadAction<ThemeId>): void {
      state.theme = action.payload
    },
    cycleSidebarState(state): void {
      state.sidebarState = CYCLE[state.sidebarState]
    },
    toggleMobileNav(state): void {
      state.mobileNavOpen = !state.mobileNavOpen
    },
    closeMobileNav(state): void {
      state.mobileNavOpen = false
    },
  },
})

export const { setTheme, cycleSidebarState, toggleMobileNav, closeMobileNav } =
  themeSlice.actions
export const themeReducer = themeSlice.reducer
