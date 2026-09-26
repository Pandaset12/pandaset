# Data-infrastructure drafts (not connected to the API)

These files preserve the earlier Backend #1 handoff work. They are incomplete
reference code, not a MongoDB implementation or an active market-data pipeline.

| File | What exists |
| --- | --- |
| `data_pipeline/DESIGN.md` | Proposed data/storage design |
| `data_pipeline/models.py` | Initial price, provenance and quant-input schemas |
| `data_pipeline/providers.py` | Fictional fixture reader and initial Twelve Data adapter |
| `data_pipeline/sample_prices.json` | Clearly fictional test prices |
| `requirements-data.txt` | Dependencies proposed for completing the data layer |

**MongoDB status:** only the design and `pymongo` dependency were written.
`mongo_store.py`, `price_store.py`, `service.py` and the proposed CLI do not
exist yet. Neither MongoDB nor Tiger Data has been connected or tested.
The current API uses `backend/storage.py` (SQLite).

The fixture reader has been smoke-tested after restoration. The live market
adapter has not been tested against a provider account. Do not enable it as a
production data source without review of provider permissions, adjustment
semantics, date coverage, error handling and credentials.

These drafts are not imported by the running API. Financial formulas remain in
the quant teammate's module. The fictional price fixture here is unrelated to
the API's precomputed demo analytics and must not be presented as their source.

See [MongoDB handoff](../docs/MONGODB_HANDOFF.md) and
[quant integration review](../docs/QUANT_REVIEW.md) for the next boundaries.
