import { useState } from "react";
import { ArrowPath as RotateCcw, Check } from "./icons";
import { assets, initialWeights } from "../../../quant/data";
import { validateWeights } from "../../../quant/analytics";
import { Modal, AssetMark } from "./UI";

export function EditPortfolio({
  weights,
  busy,
  error,
  onClose,
  onSave,
}: {
  weights: number[];
  busy: boolean;
  error: string;
  onClose: () => void;
  onSave: (w: number[]) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState([...weights]);
  const total = draft.reduce((a, b) => a + b, 0);
  const valid = validateWeights(draft);
  return (
    <Modal
      title="Save a new sample portfolio"
      onClose={busy ? () => undefined : onClose}
    >
      <p className="modal-description">
        Set the allocation for each sample asset. Saving creates a new
        portfolio; your current portfolio stays available in the selector.
        Weights should add up to 100%.
      </p>
      <div className="edit-weights">
        {assets.map((a, i) => (
          <label key={a.symbol}>
            <span>
              <AssetMark asset={a} small />
              <strong>{a.symbol}</strong>
              <small>{a.short}</small>
            </span>
            <span className="edit-weight-input">
              <input
                aria-label={`${a.symbol} portfolio allocation`}
                type="number"
                min="0"
                max="100"
                step="1"
                value={draft[i]}
                disabled={busy}
                onChange={(e) =>
                  setDraft(
                    draft.map((v, j) => (i === j ? Number(e.target.value) : v)),
                  )
                }
              />
              %
            </span>
          </label>
        ))}
      </div>
      <div className={`allocation-total ${valid ? "valid" : "invalid"}`}>
        <span>Total allocation</span>
        <strong>{Number(total.toFixed(2))}%</strong>
      </div>
      {!valid && (
        <p className="field-error" role="alert">
          Allocations must total 100%, with each value between 0% and 100%.
        </p>
      )}
      <div className="modal-actions">
        <button
          className="text-button"
          disabled={busy}
          onClick={() => setDraft([...initialWeights])}
        >
          <RotateCcw size={15} />
          Restore example
        </button>
        <button
          className="button dark"
          disabled={!valid || busy}
          onClick={() => void onSave(draft)}
        >
          {busy ? "Saving…" : "Save as new portfolio"}
          <Check size={16} />
        </button>
      </div>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <p className="small-text muted">
        The new portfolio is saved to your account.
      </p>
    </Modal>
  );
}
