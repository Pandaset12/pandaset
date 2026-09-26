import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { ArrowUpRight, X, ArrowRight } from "lucide-react";
import type { Asset } from "../data";
export function Brand() {
  return (
    <a href="#/" className="brand" aria-label="PortfolioLens home">
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <path d="M5 26V7h10a7 7 0 0 1 0 14h-4M20 5v22h8" />
      </svg>
      <span>
        Portfolio<span className="brand-light">Lens</span>
      </span>
    </a>
  );
}
export function AssetMark({
  asset,
  small = false,
}: {
  asset: Asset;
  small?: boolean;
}) {
  return (
    <span
      className={`asset-mark ${small ? "small" : ""}`}
      style={{ "--asset-color": asset.color } as React.CSSProperties}
      aria-hidden="true"
    >
      {asset.symbol === "MSFT" ? (
        <span className="ms-grid">
          <i />
          <i />
          <i />
          <i />
        </span>
      ) : asset.symbol === "NVDA" ? (
        "N"
      ) : asset.symbol === "VTI" ? (
        "V"
      ) : asset.symbol === "TLT" ? (
        "iS"
      ) : asset.symbol === "GLD" ? (
        "Au"
      ) : asset.symbol === "JPM" ? (
        "J"
      ) : asset.symbol === "AMD" ? (
        "A"
      ) : (
        <svg viewBox="0 0 24 24">
          <path
            d="M15.4 3.3c-.9.1-2 .6-2.6 1.3-.6.7-1.1 1.7-.9 2.7 1 .1 2-.5 2.7-1.2.6-.8 1-1.7.8-2.8ZM18.5 14.8c-.5 1.3-.8 1.9-1.5 3-1 1.5-2.5 3.4-4.2 3.4-1.5 0-1.9-.9-3.9-.9s-2.5.9-3.9.9c-1.6 0-3.1-1.7-4.1-3.2-2.8-4.2-3.1-9.1-1.4-11.6C.7 4.6 2.8 3.6 4.8 3.6c1.5 0 2.5.9 3.8.9s2.1-.9 3.8-.9c1.6 0 3.3.9 4.4 2.3-3.8 2.1-3.2 7.5 1.7 8.9Z"
            transform="translate(4 4) scale(.75)"
          />
        </svg>
      )}
    </span>
  );
}
export function SectionTitle({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}
export function TextLink({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) {
  return (
    <a className="text-link" href={to}>
      {children}
      <ArrowUpRight size={16} />
    </a>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-symbol">⌕</div>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const previous = document.activeElement as HTMLElement;
    dialog.showModal();
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = old;
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      className={`modal ${wide ? "wide" : ""}`}
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-inner">
        <div className="modal-heading">
          <h2 id="modal-title">{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
export function PageHeading({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <h1 tabIndex={-1}>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children && <div className="heading-actions">{children}</div>}
    </header>
  );
}
export function NextStep({
  title,
  body,
  to,
  label,
}: {
  title: string;
  body: string;
  to: string;
  label: string;
}) {
  return (
    <div className="next-step">
      <div>
        <h3>{title}</h3>
        <p>{body}</p>
      </div>
      <a className="button dark" href={to}>
        {label}
        <ArrowRight size={17} />
      </a>
    </div>
  );
}
