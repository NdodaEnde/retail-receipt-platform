// Which address serves what (see CLAUDE.md → Domains):
//   www.klpit.co.za  — marketing site + admin/stats
//   app.klpit.co.za  — customer app (reports, home-screen app, code sign-in)
// Same build serves both; this decides where each page belongs. Hosts not listed
// here (localhost, previews) are left alone.

export const APP_HOST = "app.klpit.co.za";
export const SITE_HOST = "www.klpit.co.za";
// Same build, not canonical: everything here moves to www. (or app. for /my).
const ALIAS_HOSTS = ["klpit.co.za", "klpit-web.onrender.com"];

const isAppPath = (path) => path === "/my" || path.startsWith("/my/");

// Returns the URL to move to, or null to stay put.
export function hostRedirect({ protocol, hostname, pathname, search }) {
  const known = hostname === APP_HOST || hostname === SITE_HOST || ALIAS_HOSTS.includes(hostname);
  if (!known) return null;
  if (hostname === APP_HOST && pathname === "/") return `/my${search}`;
  const want = isAppPath(pathname) ? APP_HOST : SITE_HOST;
  return hostname === want ? null : `${protocol}//${want}${pathname}${search}`;
}
