// Keep dashboard bookmarks and auth callbacks working at the site's original entry.
export function landingRedirect(href: string): string | null {
  const current = new URL(href);
  const fragment = new URLSearchParams(current.hash.slice(1));
  const dashboardRoute =
    /^#\/(?:$|\?|risk(?:$|\?)|research(?:$|\?)|what-if(?:$|\?))/.test(
      current.hash,
    );
  const authCallback =
    fragment.has("access_token") ||
    fragment.has("error_description") ||
    current.searchParams.has("code");
  if (!dashboardRoute && !authCallback) return null;

  const destination = new URL("app.html", current);
  destination.search = current.search;
  destination.hash = current.hash;
  return destination.href;
}
