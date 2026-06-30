'use client'

import { useState } from 'react'
import { Provider } from 'react-redux'
import { makeStore, setupStoreListeners, type AppStore } from './store'

interface StoreProviderProps {
  children: React.ReactNode
}

export function StoreProvider({ children }: StoreProviderProps) {
  const [store] = useState<AppStore>(() => {
    const created = makeStore()
    setupStoreListeners(created)
    return created
  })
  return <Provider store={store}>{children}</Provider>
}
