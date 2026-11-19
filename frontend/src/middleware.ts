import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Studio Gatekeeper Middleware
 *
 * ANTI-REDIRECT-LOOP RULE:
 * Do NOT blind-redirect /login -> /dashboard on cookie presence alone.
 * Expired or invalid cookies will cause an infinite loop if middleware redirects to /dashboard
 * while /dashboard or /api/v1/auth/me rejects with 401. Session validation is verified
 * client-side by useAuth or during SSR data-fetching.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const sessionCookie = request.cookies.get("movieai_session")?.value;

  // Protected application routes
  const isProtectedRoute = pathname.startsWith("/dashboard") || pathname.startsWith("/projects");

  if (isProtectedRoute && !sessionCookie) {
    const loginUrl = request.nextUrl.clone();
    const forwardedHost = request.headers.get("x-forwarded-host") || request.headers.get("host");
    const forwardedProto = request.headers.get("x-forwarded-proto") || "https";
    if (forwardedHost) {
      // Split host and optional port if present
      const [hostname, port] = forwardedHost.split(":");
      loginUrl.hostname = hostname;
      loginUrl.port = port || "";
      loginUrl.protocol = forwardedProto.endsWith(":") ? forwardedProto : `${forwardedProto}:`;
    }
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for:
     * - api routes (/api/...)
     * - Next.js internal files (_next/static, _next/image, favicon.ico)
     * - static files with extensions (png, svg, jpg, woff, etc.)
     */
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)",
  ],
};
