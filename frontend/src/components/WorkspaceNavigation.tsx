import { useEffect, useRef, useState } from "react";
import { Bars3, XMark } from "./icons";
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
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => setMenuOpen(false), [route]);

  useEffect(() => {
    if (!menuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setMenuOpen(false);
      menuButton.current?.focus();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  return (
    <aside className={`workspace-navigation${menuOpen ? " is-open" : ""}`}>
      <div className="workspace-navigation-brand">
        <Brand />
        <button
          ref={menuButton}
          className="workspace-menu-toggle"
          type="button"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          aria-controls="workspace-navigation-panel"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? <XMark size={22} /> : <Bars3 size={22} />}
          <span>Menu</span>
        </button>
      </div>
      <button
        className="workspace-navigation-backdrop"
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        onClick={() => setMenuOpen(false)}
      />
      <div
        className="workspace-navigation-panel"
        id="workspace-navigation-panel"
      >
        <nav
          className="workspace-navigation-links"
          aria-label="Main navigation"
        >
          {destinations.map(([to, label]) => (
            <a
              key={to}
              href={`#${to}`}
              className={route === to ? "active" : ""}
              aria-current={route === to ? "page" : undefined}
              onClick={() => setMenuOpen(false)}
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
      </div>
    </aside>
  );
}
