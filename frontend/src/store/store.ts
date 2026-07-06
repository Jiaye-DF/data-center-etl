import { configureStore } from '@reduxjs/toolkit'
import { setupListeners } from '@reduxjs/toolkit/query'
import { baseApi } from '@/lib/api/baseApi'

// configureStore 回傳型別依 reducer / middleware 泛型推導,無法先於實作標註 →
// 以內部函式推導出 AppStore,再讓對外 makeStore 明標回傳型別
const buildStore = () =>
  configureStore({
    reducer: {
      [baseApi.reducerPath]: baseApi.reducer,
    },
    middleware: (getDefault) => getDefault().concat(baseApi.middleware),
  })

export type AppStore = ReturnType<typeof buildStore>
export type RootState = ReturnType<AppStore['getState']>
export type AppDispatch = AppStore['dispatch']

export function makeStore(): AppStore {
  return buildStore()
}

export function setupStoreListeners(store: AppStore): void {
  setupListeners(store.dispatch)
}
