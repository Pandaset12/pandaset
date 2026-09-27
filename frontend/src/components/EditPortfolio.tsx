import { useId, useState } from "react";
import { ArrowPath as RotateCcw, Check } from "./icons";
import type { Asset } from "../../../quant/data";
import {
  formatPercentage,
  MAX_HOLDINGS,
  parsePercentage,
} from "./onboarding/portfolioDraft";
import { TickerSearch, type SearchTickers } from "./onboarding/TickerSearch";
import { parsePercentageDraft, workspaceAsset } from "../workspace/holdings";
import { Modal, AssetMark } from "./UI";

type Row = { asset: Asset; percentage: string };

export function EditPortfolio({
  weights,
  holdings,
  busy,
  error,
  searchTickers,
  verifyTicker,
  onClose,
  onSave,
}: {
  weights: number[];
  holdings: Asset[];
  busy: boolean;
  error: string;
  searchTickers: SearchTickers;
  verifyTicker?: (symbol: string) => Promise<void>;
  onClose: () => void;
  onSave: (weights: number[], symbols: string[]) => Promise<boolean>;
}) {
  const inputId = useId();
  const initialRows = () =>
    holdings.map((asset, index) => ({
      asset,
      percentage: String(weights[index]),
    }));
  const [rows, setRows] = useState<Row[]>(initialRows);
  const values = parsePercentageDraft(rows.map(({ percentage }) => percentage));
  const valid =
    values !== null &&
    rows.every(({ percentage }) => parsePercentage(percentage) !== null);
  const totalUnits = rows.reduce(
    (sum, row) => sum + (parsePercentage(row.percentage, true) ?? 0),
    0,
  );
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const locked = busy || saving;

  return (
    <Modal title="Edit portfolio" onClose={locked ? () => undefined : onClose}>
      <p className="modal-description">
        Add or remove holdings and set their allocations. Saving updates this
        portfolio.
      </p>
      <div className="edit-weights">
        {rows.map(({ asset, percentage }) => (
          <div className="edit-holding-row" key={asset.symbol}>
            <span className="edit-holding-name">
              <AssetMark asset={asset} small />
              <strong>{asset.symbol}</strong>
              <small>{asset.short}</small>
            </span>
            <label className="edit-weight-input">
              <input
                aria-label={`${asset.symbol} portfolio allocation`}
                type="text"
                inputMode="decimal"
                value={percentage}
                disabled={locked}
                onChange={(event) =>
                  setRows((current) =>
                    current.map((row) =>
                      row.asset.symbol === asset.symbol
                        ? { ...row, percentage: event.target.value }
                        : row,
                    ),
                  )
                }
              />
              %
            </label>
            <button
              className="text-button"
              type="button"
              disabled={locked}
              aria-label={`Remove ${asset.symbol}`}
              onClick={() =>
                setRows((current) =>
                  current.filter((row) => row.asset.symbol !== asset.symbol),
                )
              }
            >
              Remove
            </button>
          </div>
        ))}
      </div>
      {adding ? (
        <TickerSearch
          inputId={inputId}
          selectedSymbols={rows.map(({ asset }) => asset.symbol)}
          searchTickers={searchTickers}
          verifyTicker={verifyTicker}
          disabled={locked || rows.length >= MAX_HOLDINGS}
          onSelect={(ticker) => {
            if (rows.some(({ asset }) => asset.symbol === ticker.symbol))
              return;
            setRows((current) => [
              ...current,
              {
                asset: {
                  ...workspaceAsset(ticker.symbol),
                  name: ticker.name ?? ticker.symbol,
                  short: ticker.name ?? ticker.symbol,
                },
                percentage: "",
              },
            ]);
            setAdding(false);
          }}
        />
      ) : (
        <button
          className="text-button edit-add-holding"
          type="button"
          disabled={locked || rows.length >= MAX_HOLDINGS}
          onClick={() => setAdding(true)}
        >
          + Add holding
        </button>
      )}
      <div className={`allocation-total ${valid ? "valid" : "invalid"}`}>
        <span>Total allocation</span>
        <strong>{formatPercentage(totalUnits)}%</strong>
      </div>
      {!valid && (
        <p className="field-error" role="alert">
          Enter a weight above 0% for every holding and total exactly 100%.
        </p>
      )}
      <div className="modal-actions">
        <button
          className="text-button"
          disabled={locked}
          onClick={() => {
            setRows(initialRows());
            setAdding(false);
          }}
        >
          <RotateCcw size={15} /> Restore current
        </button>
        <button
          className="button dark"
          disabled={!valid || locked}
          onClick={() => {
            if (!values) return;
            setSaving(true);
            void onSave(
              values,
              rows.map(({ asset }) => asset.symbol),
            ).finally(() => setSaving(false));
          }}
        >
          {locked ? "Saving…" : "Save changes"} <Check size={16} />
        </button>
      </div>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <p className="small-text muted">
        Changes to this portfolio are saved to your account.
      </p>
    </Modal>
  );
}
