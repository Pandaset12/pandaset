import { useState } from "react";
import { Check } from "./icons";
import { Modal, AssetMark } from "./UI";
import type { PortfolioAsset } from "../types/portfolioAsset";
import { validPercentAllocation } from "../api/eventLab";

export function EditPortfolio({
  assets,
  weights,
  busy,
  error,
  onClose,
  onSave,
}: {
  assets: PortfolioAsset[];
  weights: number[];
  busy: boolean;
  error: string;
  onClose: () => void;
  onSave: (weights: number[]) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState([...weights]);
  const total = draft.reduce((sum, value) => sum + value, 0);
  const valid = draft.length === assets.length && validPercentAllocation(draft);
  return (
    <Modal
      title="Edit saved allocation"
      onClose={busy ? () => undefined : onClose}
    >
      <p className="modal-description">
        Set each saved holding’s allocation. The total must be 100%.
      </p>
      <div className="edit-weights">
        {assets.map((asset, index) => (
          <label key={asset.symbol}>
            <span>
              <AssetMark asset={asset} small />
              <strong>{asset.symbol}</strong>
              <small>{asset.name}</small>
            </span>
            <span className="edit-weight-input">
              <input
                aria-label={`${asset.symbol} portfolio allocation`}
                type="number"
                min="0"
                max="100"
                step="0.000001"
                value={draft[index]}
                disabled={busy}
                onChange={(event) =>
                  setDraft((old) =>
                    old.map((value, i) =>
                      i === index ? Number(event.target.value) : value,
                    ),
                  )
                }
              />
              %
            </span>
          </label>
        ))}
      </div>
      <div
        className={`allocation-total ${valid ? "valid" : "invalid"}`}
        aria-live="polite"
      >
        <span>Total allocation</span>
        <strong>{Number(total.toFixed(6))}%</strong>
      </div>
      {!valid && (
        <p className="field-error" role="alert">
          Allocations must total 100%, with each value between 0% and 100%.
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <div className="modal-actions">
        <button className="button subtle" disabled={busy} onClick={onClose}>
          Cancel
        </button>
        <button
          className="button dark"
          disabled={!valid || busy}
          onClick={() => void onSave(draft)}
        >
          {busy ? "Saving…" : "Apply allocation"}
          <Check size={16} />
        </button>
      </div>
      <p className="small-text muted">
        Applying saves the allocation and creates a new analysis snapshot.
        Existing event runs retain their own baseline.
      </p>
    </Modal>
  );
}
