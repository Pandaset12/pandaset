import { isValidSymbol, normalizeSymbol } from "./onboarding/portfolioDraft";

const publishableKey = import.meta.env?.VITE_LOGO_DEV_PUBLISHABLE_KEY;

export function assetLogoUrl(
  symbol: string,
  key: string | undefined = publishableKey,
): string | null {
  const normalized = normalizeSymbol(symbol);
  const token = key?.trim();
  if (
    !token?.startsWith("pk_") ||
    !isValidSymbol(normalized) ||
    normalized.startsWith("^")
  )
    return null;

  const url = new URL(
    `https://img.logo.dev/ticker/${encodeURIComponent(normalized)}`,
  );
  url.searchParams.set("token", token);
  url.searchParams.set("size", "64");
  url.searchParams.set("fallback", "404");
  return url.toString();
}

export function hasAssetLogoProvider() {
  return Boolean(publishableKey?.trim().startsWith("pk_"));
}
