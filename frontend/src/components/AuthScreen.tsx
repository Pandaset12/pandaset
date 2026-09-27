import { useState, type FormEvent } from "react";
import type { SupabaseClient } from "@supabase/supabase-js";
import { Brand } from "./UI";
import { getSupabase } from "../lib/supabase";

type Mode = "signin" | "signup";

export function AuthScreen({
  client = getSupabase(),
}: {
  client?: SupabaseClient;
}) {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmation, setConfirmation] = useState(false);

  function changeMode(next: Mode) {
    setMode(next);
    setError("");
    setConfirmation(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    const address = email.trim();
    if (!address || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setBusy(true);
    try {
      if (mode === "signup") {
        const { data, error: authError } = await client.auth.signUp({
          email: address,
          password,
          options: { emailRedirectTo: window.location.origin },
        });
        if (authError) throw authError;
        if (!data.session) setConfirmation(true);
      } else {
        const { error: authError } = await client.auth.signInWithPassword({
          email: address,
          password,
        });
        if (authError) throw authError;
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Authentication failed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <header className="auth-header">
        <Brand />
        <span>Investor workspace</span>
      </header>
      <main className="auth-main" id="main-content">
        <section className="auth-intro">
          <h1>A clearer view of what you own.</h1>
          <p>
            Explore performance, risk, research, and scenarios in one focused
            workspace.
          </p>
          <div className="auth-sample-note">
            Pandaset currently uses illustrative portfolio data and modeled
            results.
          </div>
        </section>
        <section className="auth-card" aria-labelledby="auth-title">
          {confirmation ? (
            <>
              <h2 id="auth-title">Check your email</h2>
              <p>
                We sent a confirmation link to {email.trim()}. Follow it to
                activate your account, then sign in.
              </p>
              <button
                className="button dark auth-submit"
                onClick={() => changeMode("signin")}
              >
                Back to sign in
              </button>
            </>
          ) : (
            <>
              <h2 id="auth-title">
                {mode === "signin" ? "Welcome back" : "Create your account"}
              </h2>
              <p>
                {mode === "signin"
                  ? "Sign in to enter Pandaset."
                  : "Start with the Pandaset sample portfolio."}
              </p>
              <form onSubmit={(event) => void submit(event)} noValidate>
                <label htmlFor="auth-email">Email address</label>
                <input
                  id="auth-email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  disabled={busy}
                  required
                />
                <label htmlFor="auth-password">Password</label>
                <input
                  id="auth-password"
                  type="password"
                  autoComplete={
                    mode === "signup" ? "new-password" : "current-password"
                  }
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={busy}
                  required
                  minLength={6}
                />
                {error && (
                  <p className="auth-error" role="alert">
                    {error}
                  </p>
                )}
                <button
                  className="button dark auth-submit"
                  type="submit"
                  disabled={busy}
                >
                  {busy
                    ? "Please wait…"
                    : mode === "signin"
                      ? "Sign in"
                      : "Create account"}
                </button>
              </form>
              <p className="auth-switch">
                {mode === "signin"
                  ? "New to Pandaset?"
                  : "Already have an account?"}{" "}
                <button
                  className="text-button"
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    changeMode(mode === "signin" ? "signup" : "signin")
                  }
                >
                  {mode === "signin" ? "Create an account" : "Sign in"}
                </button>
              </p>
            </>
          )}
        </section>
      </main>
      <footer className="auth-footer">
        Sample data and modeled results · For research and illustration
      </footer>
    </div>
  );
}
