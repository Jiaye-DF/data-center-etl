import { baseApi } from '@/lib/api/baseApi'
import { unwrap, type ApiEnvelope } from '@/types/api'

export type UserRole = 'admin' | 'viewer'

/** 登入來源(模式 B 雙軌;silent re-auth 分流依據) */
export type AuthProvider = 'local' | 'sso'

export interface AuthUser {
  uid: string
  username: string
  /** 顯示名稱(SSO 姓名);無則 fallback username */
  display_name: string | null
  role: UserRole
  provider: AuthProvider
}

export interface LoginPayload {
  username: string
  password: string
}

// 後端 API base URL 單一來源在 baseApi(模組層 fail-fast);此處 re-export 維持既有 import 路徑
export { API_BASE_URL } from '@/lib/api/baseApi'

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
