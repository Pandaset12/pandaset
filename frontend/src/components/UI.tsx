import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { ArrowRight, ArrowUpRight, XMark } from "./icons";
import type { Asset } from "../../../quant/data";

export function PandaMark({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 40 40"
      aria-hidden="true"
      focusable="false"
    >
      <circle className="panda-dark" cx="9" cy="9" r="6" />
      <circle className="panda-dark" cx="31" cy="9" r="6" />
      <path
        className="panda-face"
        d="M20 5.5c-8.7 0-14.5 6.4-14.5 15.1 0 8.1 6.4 14.2 14.5 14.2s14.5-6.1 14.5-14.2C34.5 11.9 28.7 5.5 20 5.5Z"
      />
      <ellipse
        className="panda-dark"
        cx="13.7"
        cy="19.5"
        rx="3.2"
        ry="4.8"
        transform="rotate(25 13.7 19.5)"
      />
      <ellipse
        className="panda-dark"
        cx="26.3"
        cy="19.5"
        rx="3.2"
        ry="4.8"
        transform="rotate(-25 26.3 19.5)"
      />
      <circle className="panda-eye" cx="14" cy="19.5" r="1.25" />
      <circle className="panda-eye" cx="26" cy="19.5" r="1.25" />
      <path
        className="panda-dark"
        d="M17.5 25c0-1.5 5-1.5 5 0s-1.1 2-2.5 2-2.5-.5-2.5-2Z"
      />
      <path
        className="panda-mouth"
        d="M20 27v1.5m0 0c-1.2 1.2-2.5 1.2-3.5 0m3.5 0c1.2 1.2 2.5 1.2 3.5 0"
      />
    </svg>
  );
}

export function Brand() {
  return (
    <a href="#/" className="brand" aria-label="PandaSet home">
      <PandaMark className="panda-mark" />
      <span>
        Panda<span className="brand-light">Set</span>
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
      ) : asset.symbol === "AAPL" ? (
        <svg viewBox="0 0 24 24">
          <path
            d="M15.4 3.3c-.9.1-2 .6-2.6 1.3-.6.7-1.1 1.7-.9 2.7 1 .1 2-.5 2.7-1.2.6-.8 1-1.7.8-2.8ZM18.5 14.8c-.5 1.3-.8 1.9-1.5 3-1 1.5-2.5 3.4-4.2 3.4-1.5 0-1.9-.9-3.9-.9s-2.5.9-3.9.9c-1.6 0-3.1-1.7-4.1-3.2-2.8-4.2-3.1-9.1-1.4-11.6C.7 4.6 2.8 3.6 4.8 3.6c1.5 0 2.5.9 3.8.9s2.1-.9 3.8-.9c1.6 0 3.3.9 4.4 2.3-3.8 2.1-3.2 7.5 1.7 8.9Z"
            transform="translate(4 4) scale(.75)"
          />
        </svg>
      ) : (
        asset.symbol.slice(0, 2)
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
            <XMark size={20} />
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
