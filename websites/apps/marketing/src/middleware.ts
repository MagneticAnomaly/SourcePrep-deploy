import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Next.js Middleware — Geo-detection for PPP pricing.
 *
 * On Netlify (via @netlify/plugin-nextjs), `request.geo` is populated
 * automatically from Netlify's edge network. On Vercel, it uses their
 * geo headers. In local dev, it defaults to empty (Band 0 / US pricing).
 *
 * Sets a `visitor_country` cookie so the client-side pricing page can
 * read the country without an extra API call.
 *
 * Test locally with: /pricing?country=IN
 */
export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  // Geo object is populated by Netlify/Vercel edge at deploy time.
  // In local dev, request.geo is undefined — defaults to empty string.
  const country = request.geo?.country || "";

  if (country) {
    response.cookies.set("visitor_country", country, {
      path: "/",
      maxAge: 60 * 60, // 1 hour — re-detect on next visit
      sameSite: "lax",
      httpOnly: false, // Needs to be readable by client JS
    });
  }

  return response;
}

export const config = {
  matcher: ["/pricing"],
};
