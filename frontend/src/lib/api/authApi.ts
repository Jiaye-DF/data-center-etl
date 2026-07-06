import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

export type UserRole = 'admin' | 'viewer'

/** 登入來源(模式 B 雙軌;silent re-auth 分流依據) */
export type AuthProvider = 'local' | 'sso'

export interface AuthUser {
  uid: string
  username: string
  role: UserRole
  provider: AuthProvider
}

export interface LoginPayload {
  username: string
  password: string
}

/** 後端 API base URL(與 baseApi 同源;供 SSO 登入 / 登出等整頁跳轉組 URL 用) */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

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
