import { NextResponse, type NextRequest } from "next/server";

import { auth0 } from "@/lib/auth0";

export async function proxy(request: NextRequest) {
  // The public product page does not require an authentication session.
  if (request.nextUrl.pathname === "/") return NextResponse.next();
  return auth0.middleware(request);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\..*).*)",
  ],
};
