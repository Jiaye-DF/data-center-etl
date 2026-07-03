import { baseApi } from '@/lib/api/baseApi'

/** 後端統一回應信封(FastAPI `ApiResponse[T]`) */
interface ApiEnvelope<T> {
  success: boolean
  data: T | null
  detail: string | null
  response_code: number
}

export type UserRole = 'admin' | 'viewer'

export interface AuthUser {
  uid: string
  username: string
  role: UserRole
}

export interface LoginPayload {
  username: string
  password: string
}

/** 後端 API base URL(與 baseApi 同源;供 SSO 登入 / 登出等整頁跳轉組 URL 用) */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

function unwrap<T>(envelope: ApiEnvelope<T>): T {
  if (envelope.data === null) {
    throw new Error(envelope.detail ?? 'empty_response')
  }
  return envelope.data
}

export const authApi = baseApi
  .enhanceEndpoints({ addTagTypes: ['Auth'] })
  .injectEndpoints({
    endpoints: (build) => ({
      // 認證走 httpOnly cookie(baseApi credentials: 'include'),前端不觸碰 token
      getMe: build.query<AuthUser, void>({
        query: () => '/auth/me',
        providesTags: ['Auth'],
        transformResponse: (response: ApiEnvelope<AuthUser>): AuthUser =>
          unwrap(response),
      }),
      login: build.mutation<AuthUser, LoginPayload>({
        query: (body) => ({ url: '/auth/login', method: 'POST', body }),
        invalidatesTags: ['Auth'],
        transformResponse: (response: ApiEnvelope<AuthUser>): AuthUser =>
          unwrap(response),
      }),
    }),
  })

export const { useGetMeQuery, useLoginMutation } = authApi
