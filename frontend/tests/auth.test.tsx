import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { JSDOM } from "jsdom";
import type { Session, SupabaseClient } from "@supabase/supabase-js";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  MutationObserver: dom.window.MutationObserver,
});

const { createElement } = await import("react");
const { cleanup, fireEvent, render, screen, waitFor } =
  await import("@testing-library/react");
const { AuthBoundary } = await import("../src/components/AuthBoundary");
const { AuthScreen } = await import("../src/components/AuthScreen");

after(() => dom.window.close());

function mockClient(initial: Session | null = null) {
  let listener: ((_event: string, session: Session | null) => void) | undefined;
  let resolveSession:
    | ((value: {
        data: { session: Session | null };
        error: Error | null;
      }) => void)
    | undefined;
  const calls = {
    signin: 0,
    signup: 0,
    signupOptions: undefined as unknown,
    signout: 0,
    unsubscribed: 0,
  };
  const auth = {
    getSession: () =>
      new Promise((resolve: typeof resolveSession) => {
        resolveSession = resolve;
      }),
    onAuthStateChange: (callback: typeof listener) => {
      listener = callback;
      return {
        data: {
          subscription: {
            unsubscribe: () => {
              calls.unsubscribed++;
            },
          },
        },
      };
    },
    signInWithPassword: async () => {
      calls.signin++;
      return { error: null };
    },
    signUp: async (options: unknown) => {
      calls.signup++;
      calls.signupOptions = options;
      return { data: { session: null }, error: null };
    },
    signOut: async () => {
      calls.signout++;
      listener?.("SIGNED_OUT", null);
      return { error: null };
    },
  };
  return {
    client: { auth } as unknown as SupabaseClient,
    calls,
    restore: () =>
      resolveSession?.({ data: { session: initial }, error: null }),
    failRestore: () =>
      resolveSession?.({
        data: { session: null },
        error: new Error("Session restore failed"),
      }),
    emit: (session: Session | null) => listener?.("SIGNED_IN", session),
    failSignIn: () => {
      auth.signInWithPassword = async () => {
        calls.signin++;
        return { error: new Error("Invalid credentials") };
      };
    },
  };
}

const session = { access_token: "test" } as Session;

function mountBoundary(client: SupabaseClient) {
  return render(
    createElement(AuthBoundary, {
      client,
      renderDashboard: (_session: Session, signOut: () => Promise<void>) =>
        createElement(
          "div",
          {},
          createElement("span", {}, "Dashboard"),
          createElement(
            "button",
            { onClick: () => void signOut() },
            "Sign out",
          ),
        ),
      renderSignedOut: () => createElement("span", {}, "Sign in required"),
    }),
  );
}

test("restores a persisted session before showing the dashboard", async () => {
  const mock = mockClient(session);
  const view = mountBoundary(mock.client);
  assert.match(screen.getByRole("status").textContent ?? "", /Restoring/);
  assert.equal(screen.queryByText("Dashboard"), null);
  mock.restore();
  await waitFor(() => assert.ok(screen.getByText("Dashboard")));
  view.unmount();
  assert.equal(mock.calls.unsubscribed, 1);
  cleanup();
});

test("shows the signed-out screen and responds to auth changes and sign-out", async () => {
  const mock = mockClient();
  render(
    createElement(AuthBoundary, {
      client: mock.client,
      renderDashboard: (_session: Session, signOut: () => Promise<void>) =>
        createElement("button", { onClick: () => void signOut() }, "Sign out"),
      renderSignedOut: () => createElement("span", {}, "Sign in required"),
    }),
  );
  mock.restore();
  await waitFor(() => assert.ok(screen.getByText("Sign in required")));
  mock.emit(session);
  await waitFor(() =>
    assert.ok(screen.getByRole("button", { name: "Sign out" })),
  );
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() => assert.ok(screen.getByText("Sign in required")));
  assert.equal(mock.calls.signout, 1);
  cleanup();
});

test("sign-in validates input and handles success and failure", async () => {
  const mock = mockClient();
  render(createElement(AuthScreen, { client: mock.client }));
  fireEvent.click(screen.getByRole("button", { name: "Sign in", exact: true }));
  assert.match(screen.getByRole("alert").textContent ?? "", /valid email/);
  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "investor@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "password123" },
  });
  mock.failSignIn();
  fireEvent.click(screen.getByRole("button", { name: "Sign in", exact: true }));
  await waitFor(() =>
    assert.match(
      screen.getByRole("alert").textContent ?? "",
      /Invalid credentials/,
    ),
  );
  assert.equal(mock.calls.signin, 1);
  cleanup();

  const success = mockClient();
  render(createElement(AuthScreen, { client: success.client }));
  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "investor@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "password123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in", exact: true }));
  await waitFor(() => assert.equal(success.calls.signin, 1));
  assert.equal(screen.queryByRole("alert"), null);
  cleanup();
});

test("sign-up shows email confirmation when Supabase returns no session", async () => {
  const mock = mockClient();
  render(createElement(AuthScreen, { client: mock.client }));
  fireEvent.click(screen.getByRole("button", { name: "Create an account" }));
  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "investor@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "password123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));
  await waitFor(() => assert.ok(screen.getByText("Check your email")));
  assert.equal(mock.calls.signup, 1);
  assert.deepEqual(mock.calls.signupOptions, {
    email: "investor@example.com",
    password: "password123",
    options: { emailRedirectTo: window.location.origin },
  });
  cleanup();
});

test("missing Supabase configuration shows setup instructions without a reload loop", () => {
  const view = render(
    createElement(AuthBoundary, {
      renderDashboard: () => createElement("span", {}, "Dashboard"),
      renderSignedOut: () => createElement("span", {}, "Sign in required"),
    }),
  );
  const message = screen.getByRole("alert").textContent ?? "";
  assert.match(message, /authentication is not configured/i);
  assert.match(message, /VITE_SUPABASE_URL/);
  assert.match(message, /VITE_SUPABASE_PUBLISHABLE_KEY/);
  assert.match(message, /restart the frontend/i);
  assert.equal(screen.queryByText("Dashboard"), null);
  assert.equal(screen.queryByText("Sign in required"), null);
  assert.equal(screen.queryByRole("button", { name: /reload/i }), null);
  view.unmount();
  cleanup();
});

test("successful auth event clears an earlier session restoration error", async () => {
  const mock = mockClient();
  const view = mountBoundary(mock.client);
  mock.failRestore();
  await waitFor(() =>
    assert.match(
      screen.getByRole("alert").textContent ?? "",
      /Session restore failed/,
    ),
  );
  mock.emit(session);
  await waitFor(() => assert.ok(screen.getByText("Dashboard")));
  assert.equal(screen.queryByRole("alert"), null);
  view.unmount();
  cleanup();
});
