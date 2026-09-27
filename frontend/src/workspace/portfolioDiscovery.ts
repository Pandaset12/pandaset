const markerPrefix = "pandaset:known-portfolio:";

function markerKey(userId: string | undefined) {
  return userId ? `${markerPrefix}${userId}` : null;
}

export function hasKnownPortfolio(userId: string | undefined) {
  const key = markerKey(userId);
  if (!key) return false;
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

export function rememberPortfolio(userId: string | undefined) {
  const key = markerKey(userId);
  if (!key) return;
  try {
    window.localStorage.setItem(key, "1");
  } catch {
    // Discovery still works when local storage is unavailable.
  }
}

export function forgetPortfolio(userId: string | undefined) {
  const key = markerKey(userId);
  if (!key) return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Deleting the portfolio on the server has already succeeded.
  }
}
