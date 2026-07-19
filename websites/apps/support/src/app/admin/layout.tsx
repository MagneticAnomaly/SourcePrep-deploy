import { isAuthorizedServer, isConfirmedDevelopment } from '../../lib/auth';

/**
 * Admin layout — auth gate.
 *
 * If ADMIN_TOKEN is set, admits only requests carrying a valid session cookie
 * (verified constant-time by `isAuthorizedServer`). If ADMIN_TOKEN is unset,
 * access is open ONLY in a positively-confirmed dev/test env; otherwise it is
 * hard-denied with a "not configured" notice (DR-4.4).
 */
export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const token = process.env.ADMIN_TOKEN;

  // No token configured → open only in confirmed dev/test; hard-deny otherwise.
  if (!token) {
    if (!isConfirmedDevelopment()) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
          <div className="text-center">
            <h1 className="text-2xl font-bold mb-2">Admin Not Configured</h1>
            <p className="text-gray-400">Set ADMIN_TOKEN environment variable to enable admin access.</p>
          </div>
        </div>
      );
    }
    // Confirmed dev/test — open access
    return <>{children}</>;
  }

  // Token configured → require a valid session cookie.
  if (await isAuthorizedServer()) {
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
