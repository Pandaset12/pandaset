import json
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.twelve_data import ProviderUnavailable, TwelveDataPriceProvider


def rows(symbol, values):
    return {"meta": {"symbol": symbol}, "values": [
        {"datetime": day, "close": str(close)} for day, close in values
    ]}


def test_batched_history_is_sorted_aligned_and_requests_adjusted_daily(monkeypatch):
    payload = {
        "AAPL": rows("AAPL", [("2026-01-02", 102), ("2026-01-01", 100)]),
        "MSFT": rows("MSFT", [("2026-01-01", 200), ("2026-01-02", 198)]),
    }
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(payload).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("backend.twelve_data.urlopen", fake_urlopen)
    frame = TwelveDataPriceProvider("test-key", timeout_seconds=7).prices(["aapl", "msft"], 2)

    query = parse_qs(urlsplit(captured["url"]).query)
    assert query["symbol"] == ["AAPL,MSFT"]
    assert query["interval"] == ["1day"]
    assert query["outputsize"] == ["3"]
    assert query["adjust"] == ["all"]
    assert query["timezone"] == ["UTC"]
    assert query["apikey"] == ["test-key"]
    assert captured["timeout"] == 7
    assert list(frame.index.strftime("%Y-%m-%d")) == ["2026-01-01", "2026-01-02"]
    assert frame.to_dict() == {"AAPL": {frame.index[0]: 100.0, frame.index[1]: 102.0},
                               "MSFT": {frame.index[0]: 200.0, frame.index[1]: 198.0}}


def test_single_symbol_response_shape_is_supported(monkeypatch):
    provider = TwelveDataPriceProvider("test-key")
    provider._fetch = lambda symbols, outputsize: rows("AAPL", [("2026-01-02", 102), ("2026-01-01", 100)])
    frame = provider.prices(["AAPL"], 2)
    assert frame["AAPL"].tolist() == [100.0, 102.0]


def test_missing_key_does_not_call_upstream():
    provider = TwelveDataPriceProvider("")
    provider._fetch = lambda *_: pytest.fail("Must not call Twelve Data without a key")
    with pytest.raises(ProviderUnavailable, match="TWELVE_DATA_API_KEY"):
        provider.prices(["AAPL"])


def test_provider_rejects_partial_or_misaligned_history():
    provider = TwelveDataPriceProvider("test-key")
    provider._fetch = lambda *_: {
        "AAPL": rows("AAPL", [("2026-01-02", 102), ("2026-01-01", 100)]),
        "MSFT": rows("MSFT", [("2026-01-02", 200), ("2026-01-03", 201)]),
    }
    with pytest.raises(ProviderUnavailable, match="same trading dates"):
        provider.prices(["AAPL", "MSFT"])


def test_provider_rejects_invalid_or_nonpositive_values():
    provider = TwelveDataPriceProvider("test-key")
    provider._fetch = lambda *_: {"AAPL": rows("AAPL", [("2026-01-02", 0), ("2026-01-01", 100)])}
    with pytest.raises(ProviderUnavailable, match="invalid prices"):
        provider.prices(["AAPL"])
