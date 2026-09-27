import { Brand } from "./UI";

const destinations = [
  ["/", "Overview"],
  ["/risk", "Risk & exposure"],
  ["/research", "Research"],
  ["/what-if", "What-if lab"],
] as const;

export function WorkspaceNavigation({
  route,
  onSignOut,
}: {
  route: string;
  onSignOut: () => Promise<void>;
}) {
  return (
    <aside className="workspace-navigation">
      <div className="workspace-navigation-brand">
        <Brand />
      </div>
      <nav className="workspace-navigation-links" aria-label="Main navigation">
        {destinations.map(([to, label]) => (
          <a
            key={to}
            href={`#${to}`}
            className={route === to ? "active" : ""}
            aria-current={route === to ? "page" : undefined}
          >
            {label}
          </a>
        ))}
      </nav>
      <button
        className="workspace-navigation-signout"
        type="button"
        onClick={() => void onSignOut()}
      >
        Sign out
      </button>
    </aside>
  );
}
