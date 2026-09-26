import { useEffect, useState, type ReactNode } from "react";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { getSupabase } from "../lib/supabase";

export function AuthBoundary({
  client = getSupabase(),
  renderDashboard,
  renderSignedOut,
}: {
  client?: SupabaseClient;
  renderDashboard: (signOut: () => Promise<void>) => ReactNode;
  renderSignedOut: (client: SupabaseClient) => ReactNode;
}) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    let authEventReceived = false;
    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((_event, nextSession) => {
      if (!mounted) return;
      authEventReceived = true;
      setSession(nextSession);
      setLoading(false);
    });
    void client.auth
      .getSession()
      .then(({ data, error: authError }) => {
        if (!mounted || authEventReceived) return;
        if (authError) setError(authError.message);
        setSession(data.session);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!mounted || authEventReceived) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Unable to restore your session.",
        );
        setLoading(false);
      });
    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [client]);

  async function signOut() {
    const { error: authError } = await client.auth.signOut();
    if (authError) setError(authError.message);
  }

  if (loading)
    return (
      <main className="auth-loading" role="status">
        Restoring your PandaSet session…
      </main>
    );
  return (
    <>
      {error && (
        <p className="auth-global-error" role="alert">
          {error}
        </p>
      )}
      {session ? renderDashboard(signOut) : renderSignedOut(client)}
    </>
  );
}
