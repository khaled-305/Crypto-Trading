# TPB-v1 — BTC spot trend-pullback hypothesis

Status: **research only; no demonstrated edge; not approved for live trading**.
Version frozen for initial evaluation on 2026-09-24. These parameter choices are a testable starting hypothesis, not optimized or proven profitable. Changing any rule requires a new version and an entry in validation.md describing what changed and every variation tried.

## Exact signal

- Market: Bybit BTCUSDT spot, long only, no borrowing. One paper position at a time. Record overlapping signals as skipped, not additional positions.
- Candles: exchange UTC-aligned 1-hour and 4-hour candles. Only use completed candles available at signal time. Minimum warmup: 60 closed hourly candles and 200 closed 4-hour candles. Retain the dataset and its starting timestamp/hash because EMA initialization can affect results.
- EMA definition: initialize with the arithmetic mean of the first N closes; thereafter EMA = close × 2/(N+1) + previous EMA × (1−2/(N+1)).
- At each completed hourly candle t, use the latest 4-hour candle j whose closing timestamp is at or before t's close.
- Trend: 4-hour close[j] > EMA50[j], and EMA50[j] > EMA50[j−3].
- Pullback: hourly close[t−1] <= EMA20[t−1].
- Reclaim: hourly close[t] > EMA20[t] AND close[t] > high[t−1]. All five conditions must hold. No subjective chart overrides.

## Entry and exit model

- Signal reference price: close[t]. The entry opportunity expires 60 seconds after t closes. Maximum quoted ask for an entry attempt is close[t]; if the first actionable quote is higher, record a missed entry and do not chase. A paper market fill includes adverse slippage above the ask; model that separately in the risk calculator.
- Initial stop: minimum low of hourly candles t−2, t−1, t, rounded down to the price tick, minus one price tick. No entry if stop is nonpositive or at/above entry.
- Fixed target: close[t] + 3 × (close[t] − stop), rounded down to the price tick. This is a hypothesis to test, not evidence that price will reach it. Do not move it to rescue the ratio. Net reward/risk must still be >=2 after modeled costs, rounding, and actual entry quote.
- Entire sellable position exits at the first of stop, target, or a time exit 12 hours after entry. No partial profit-taking, trailing stop, averaging down, or discretionary breakeven move in v1. Normal account protection and execution-failure handling still apply.
- The entry, protective exit, and target must satisfy current instrument restrictions and the approved risk budgets. Default risk remains 0.5%; a passing math check does not grant live eligibility.
- Skip if account reconciliation, fees, stop support, data freshness, liquidity/slippage assumptions, or minimum sizes cannot be established. Record the specific reason for every skip.
- No discretionary news filter is part of the tested hypothesis. Record known macro events as context. Any proposed event exclusion must specify exact sources/times/window before evaluation and become a new strategy version; do not selectively remove losing event trades afterward.

## Honest historical and forward evaluation

tools/strategy.py extracts historical signals only. tools/backtest.py separately models approximate historical fills, positions, costs, and outcomes using those signals. It does not validate real fills or grant live eligibility. A recent 1,000-candle download is not a sufficient validation dataset by itself. Usage and model limitations are in research.md.

For a historical execution simulation, only the next available quote/open after signal close can be an entry, not the candle close learned after it happens. Hourly candles cannot establish a 60-second entry window or order-book fills: obtain finer data or mark the result as an approximation ineligible for live promotion. If stop and target are touched in the same candle and finer data cannot resolve order, assume the adverse stop happens first. A gap below stop exits at the worse available price, plus costs. A target touch alone does not prove a resting limit filled. Model taker costs conservatively unless maker fills are evidenced. Use actual fee currency and net inventory.

Forward paper trades use timestamped public mainnet observations; testnet execution can test mechanics but does not prove mainnet fill quality. Record signal time, first actionable quote, quote age, planned and modeled fills, and missed/partial fills. Never present a simulated fill as an actual exchange execution.
