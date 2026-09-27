import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | undefined;

export class SupabaseConfigurationError extends Error {
  constructor() {
    super(
      "Pandaset authentication is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY, then restart the frontend.",
    );
    this.name = "SupabaseConfigurationError";
  }
}

export function getSupabase(): SupabaseClient {
  if (client) return client;
  const url = import.meta.env?.VITE_SUPABASE_URL;
  const publishableKey = import.meta.env?.VITE_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !publishableKey) {
    throw new SupabaseConfigurationError();
  }
  client = createClient(url, publishableKey);
  return client;
}
