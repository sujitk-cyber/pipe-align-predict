import { NextRequest, NextResponse } from "next/server"

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  // Demo-mode bypass for screenshot automation
  if (req.cookies.get("ww-demo")?.value === "1") return NextResponse.next()

  // Always allow auth API routes
  if (pathname.startsWith("/api/auth")) return NextResponse.next()

  const isLoginPage = pathname === "/login"

  // Check for any NextAuth session cookie (dev or prod name)
  const hasSession =
    !!req.cookies.get("authjs.session-token")?.value ||
    !!req.cookies.get("__Secure-authjs.session-token")?.value

  if (!hasSession && !isLoginPage) {
    return NextResponse.redirect(new URL("/login", req.url))
  }
  if (hasSession && isLoginPage) {
    return NextResponse.redirect(new URL("/", req.url))
  }

  return NextResponse.next()
}

// Narrow matcher — only protect actual page routes, not static assets
export const config = {
  matcher: ["/", "/jobs/:path*", "/settings"],
}
