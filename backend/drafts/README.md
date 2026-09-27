# Data-infrastructure drafts (not connected to the API)

These files preserve the earlier Backend #1 handoff work. They are incomplete
reference code, not a MongoDB implementation or an active market-data pipeline.

| File | What exists |
| --- | --- |
| `data_pipeline/DESIGN.md` | Proposed data/storage design |
| `data_pipeline/models.py` | Initial price, provenance and quant-input schemas |
| `data_pipeline/providers.py` | Fictional fixture reader; the obsolete vendor adapter was removed |
| `data_pipeline/sample_prices.json` | Clearly fictional test prices |
| `requirements-data.txt` | Dependencies proposed for completing the data layer |

**Historical draft status:** these drafts only contained the MongoDB design and
`pymongo` dependency, with no implemented store or CLI. Current main separately
implements `backend/mongo_store.py` for the gated v2 event lab. V1 still uses
`backend/storage.py` (SQLite). Restoring these drafts does not configure either
store, migrate v1 portfolios, or connect Tiger Data.

The fixture reader has been smoke-tested after restoration. The active Alpaca
history adapter lives in `backend/alpaca_history.py` outside this draft.

The draft Python modules are not imported by the running API. However, the active
`SamplePriceProvider` reads `data_pipeline/sample_prices.json` and passes those
fictional prices to the quant engine for custom sample-mode analyses. That path
is separate from the precomputed `fixtures/demo_analytics.json` used by legacy
regression tests. Financial formulas remain in the quant teammate's module.

See [MongoDB handoff](../docs/MONGODB_HANDOFF.md) and
[quant integration review](../docs/QUANT_REVIEW.md) for the next boundaries.
