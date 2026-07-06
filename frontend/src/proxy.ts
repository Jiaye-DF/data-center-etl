import { NextResponse, type NextRequest } from 'next/server'

/** 後端設定的 JWT httpOnly cookie 名稱(前端僅判斷存在與否,禁讀寫內容) */
const JWT_COOKIE_NAME = 'access_token'

/** 免登入路徑 */
const PUBLIC_PATHS = ['/login']

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  )
}

// auth guard:無 cookie 一律導向 /login(cookie 有效性由頁面層 /me 驗證,避免舊 cookie 造成導向迴圈)
export function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl
  if (isPublicPath(pathname)) {
    return NextResponse.next()
  }
  if (!request.cookies.has(JWT_COOKIE_NAME)) {
    const loginUrl = new URL('/login', request.url)
    if (pathname !== '/') {
      loginUrl.searchParams.set('next', pathname)
    }
    return NextResponse.redirect(loginUrl)
  }
  return NextResponse.next()
}

export const config = {
  // 排除 Next 靜態資源與帶副檔名的檔案(favicon 等)
  matcher: ['/((?!_next/static|_next/image|.*\\..*).*)'],
}
