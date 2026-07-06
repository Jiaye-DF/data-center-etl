import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

// 模組層 fail-fast:缺值即 build / 啟動時直接炸,禁靜默把 localhost 烘進 bundle
// (本地 dev 由 frontend/.env.local 提供;部署由 image build args 提供)
const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL
if (apiBaseUrl === undefined || apiBaseUrl === '') {
  throw new Error(
    'NEXT_PUBLIC_API_URL 未設定:本地 dev 請建立 frontend/.env.local,部署請於 build args 傳入',
  )
}

/** 後端 API base URL(供 SSO 登入 / 登出等整頁跳轉組 URL 用) */
export const API_BASE_URL: string = apiBaseUrl

export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: API_BASE_URL,
    credentials: 'include',
  }),
  tagTypes: [],
  endpoints: () => ({}),
})
