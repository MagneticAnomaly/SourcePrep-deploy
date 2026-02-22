import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { COOKIE_NAME } from '../../lib/auth';

/**
 * Admin layout — auth gate.
 *
 * If ADMIN_TOKEN is set, checks for:
 * 1. ?token= query param → sets cookie + redirects without param
 * 2. admin_token cookie
 *
 * In dev (no ADMIN_TOKEN), access is open.
 */
export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const token = process.env.ADMIN_TOKEN;

  // No token configured → allow in dev
  if (!token) {
    if (process.env.NODE_ENV === 'production') {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
          <div className="text-center">
            <h1 className="text-2xl font-bold mb-2">Admin Not Configured</h1>
            <p className="text-gray-400">Set ADMIN_TOKEN environment variable to enable admin access.</p>
          </div>
        </div>
      );
    }
    // Dev mode — open access
    return <>{children}</>;
  }

  // Check cookie
  const cookieStore = await cookies();
  const cookieToken = cookieStore.get(COOKIE_NAME)?.value;

  if (cookieToken === token) {
    return <>{children}</>;
  }

  // No valid auth — show login form
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
      <div className="w-full max-w-sm p-8">
        <h1 className="text-2xl font-bold mb-6 text-center">Admin Access</h1>
        <form action="/admin/auth" method="POST">
          <label className="block text-sm text-gray-400 mb-2">Admin Token</label>
          <input
            type="password"
            name="token"
            autoFocus
            className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter admin token..."
          />
          <button
            type="submit"
            className="w-full mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors"
          >
            Sign In
          </button>
        </form>
      </div>
    </div>
  );
}
