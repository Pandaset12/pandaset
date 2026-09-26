import { useState } from "react";
import { ArrowPath as RotateCcw, Check } from "./icons";
import { assets, initialWeights } from "../../../quant/data";
import { validateWeights } from "../../../quant/analytics";
import { Modal, AssetMark } from "./UI";

export function EditPortfolio({
  weights,
  onClose,
  onSave,
}: {
  weights: number[];
  onClose: () => void;
  onSave: (w: number[]) => void;
}) {
  const [draft, setDraft] = useState([...weights]);
  const total = draft.reduce((a, b) => a + b, 0);
  const valid = validateWeights(draft);
  return (
    <Modal title="Edit your sample portfolio" onClose={onClose}>
      <p className="modal-description">
        Set the allocation for each asset. Your weights should add up to 100%.
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
          onClick={() => setDraft([...initialWeights])}
        >
          <RotateCcw size={15} />
          Restore example
        </button>
        <button
          className="button dark"
          disabled={!valid}
          onClick={() => onSave(draft)}
        >
          Update portfolio
          <Check size={16} />
        </button>
      </div>
      <p className="small-text muted">
        Changes stay in this session. Reloading restores the example portfolio.
      </p>
    </Modal>
  );
}
