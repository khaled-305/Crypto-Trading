# Trading account

- Initial capital: $100; reconcile current equity before each session.
- Exchange: Bybit.
- Maximum risk per trade: 2% of current equity, including estimated costs ($2 initially).
- Default planned risk per trade: 0.5% of current equity ($0.50 initially).
- Total open-risk cap: 1% of current equity, including pending entries ($1 initially). This tighter cap also constrains individual trades.
- Daily loss limit: 2% of day-start equity ($2 for a day starting at $100).
- Weekly loss limit: 4% of week-start equity ($4 for a week starting at $100).
- Reset boundaries: 00:00 daily and Monday 00:00 weekly, Africa/Lagos time. Apply the loss accounting and halt rules in AGENTS.md.
- Products: spot only initially; no leverage or borrowing.
- Timeframes: mix preferred; begin with 4-hour context and 1-hour entry signals.
- Watchlist: recommend based on current evidence and available Bybit spot pairs; exclusions not yet specified.
- Minimum risk/reward: 1:2 after estimated costs across the entire exit allocation.
- Quote currency: USDT (user confirmed).
- Displayed Spot fees: maker 0.1000%, taker 0.1000%, Regular User, MNT discount off; user screenshot received 2026-09-24. Supported stop/order types and current pair constraints remain pending.

## Session — 2026-09-24, 12:12 Africa/Lagos

- Status: research only; no entry recommended or order placed. Actual account positions and P&L remain unconfirmed.
- Bybit BTC/USDT spot snapshot at 11:11:53 UTC (12:11:53 Lagos): last 83,529.1 USDT; 24-hour change -2.58%; range 82,858–85,946.9; turnover approximately 609.18 million USDT; best bid/ask 83,529.1/83,529.2. This is a snapshot, not a streaming feed or full order book. Source: https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT
- CoinGecko aggregate snapshot at 11:04:19 UTC: BTC dominance 59.24%, ETH 11.42%; market capitalization change -6.32% over 24 hours; reported volume approximately $119.25 billion. A single snapshot does not establish a dominance trend. Source: https://api.coingecko.com/api/v3/global
- BEA calendar: international transactions/investment position release September 24; GDP and personal income/outlays September 30. Source: https://www.bea.gov/news/schedule
- BTC/USDT is a watch candidate only. Candle retrieval failed; ETH/SOL quotes were unavailable. No validated entry, stop, target, or position size. No historical/paper-test evidence has been supplied for a live-eligible setup.
- Await account reconciliation, actual fees, supported stop types, and current BTC/USDT 4-hour/1-hour chart data and bid/ask before building a conditional paper plan. Do not infer remaining loss allowances from initial capital alone.

### Account confirmation — subsequent user check-in

- User confirms equity is still $100, with the full balance available in USDT (reported as 100 USDT), no open positions, and no trades this week.
- Default planned risk: $0.50 equivalent including estimated costs; total open-risk cap: $1 equivalent. These are risk budgets, not position notionals.
- Pending entry orders and prior daily/weekly halt status have not been explicitly confirmed. Do not infer those from available balance alone.
- Actual account fee rates, supported stop types, and current chart data remain needed. Earlier market snapshots must be refreshed before an entry plan; no trade has been recommended or placed.

## Approved research and security implementation — 2026-09-24

- Mandatory external-resource security review added to AGENTS.md; reviews and approved scopes are recorded in security-review.md. No external skill, SDK, or package installed; Bybit AI Trading Skill remains unapproved for execution.
- Added a fixed research strategy (strategy.md), public data collector, signal evaluator, fee-aware paper risk calculator, and append-only paper signal/outcome ledger. Usage: research.md.
- TPB-v1 remains unvalidated and not live-eligible. No paper or live trades have been invented or opened. Historical execution simulation and forward evidence remain outstanding in validation.md.
- Public API connectivity check timed out after 25 seconds; no current data accepted. Prior session quotes are historical observations only.

## Historical simulator and access diagnosis — 2026-09-24

- Added staged DNS/TLS/API diagnostics, a paginated historical candle downloader, and an exploratory historical trade simulator. The strategy rules and account limits remain unchanged.
- Diagnostic at 15:16:38 UTC stopped at DNS after 12 seconds. No configured proxy was detected. User confirmed browser error DNS_PROBE_FINISHED_NXDOMAIN. A local cache flush succeeded; the 15:19:34 UTC diagnostic still failed at DNS. No hosts-file override was found. Data access is not fixed or verified.
- Simulator tests use synthetic cases only. Historical assumptions and full-fill approximations are explicit; no profitability, actual fills, or live readiness is claimed. No actual trades entered in this session.

## Account fee evidence — 2026-09-24

- User-provided My Fee Rates screenshot: Regular User; Spot maker 0.1000%, taker 0.1000%; MNT discount toggle off. Use 0.001 as the decimal rate for each side under this displayed schedule.
- Evidence is a user screenshot received today, not an authenticated API response or dated historical fee record; screenshot capture time is unknown. No credentials requested or extracted. Actual charged fee currency and pair-specific exceptions are not established by this image.
- Existing historical report/config remain unchanged: their rates numerically match this display, but today's account evidence does not verify the historical period or the illustrative instrument/spread/slippage assumptions.

## Current BTCUSDT spot constraints — 2026-09-24 22:11:55 Africa/Lagos

- Reviewed public instruments-info endpoint returned Trading status. Evidence: instrument-btc-20260924.json, received 21:11:55 UTC with raw-response hash and source URL.
- Price tick: 0.1 USDT; base quantity precision: 0.000001 BTC; quote precision: 0.0000001 USDT; minimum order amount: 5 USDT.
- Maximum limit order quantity: 230 BTC; maximum market order quantity: 120 BTC; post-only maximum limit size: 1150 BTC. These are exchange ceilings, not approved account position sizes.
- Current documentation deprecates minOrderQty, maxOrderQty and maxOrderAmt; retain raw fields for provenance but use current minimum amount and order-type-specific maxima for checks. Price-band parameters are included in the response; their dynamic application is not implemented by the exploratory risk calculator.
- The example backtest configuration uses a 0.01 price tick, which differs from today's 0.1 tick. It remains an illustrative historical configuration, not verified current rules; prior results are preserved. Current rules do not establish historical rules.
- Account-specific TP/SL availability, trigger/exit type, reservation and cancellation behavior remain unverified. No order submitted.

## TP/SL interface evidence — 2026-09-25

- User screenshot shows BTC/USDT Spot, Sell selected, Margin toggle off, TP/SL form and execution dropdown offering Limit and Market. Trigger Price and Quantity are blank; Limit is currently selected. The displayed price is not an approved trade level.
- Earlier menu screenshot also shows Conditional, OCO and Trailing Stop options. This establishes visible interface choices only, not exchange acceptance or execution behavior.
- Subsequent screenshot received 2026-09-25 shows Market selected within the TP/SL Sell form, blank Trigger Price and BTC Quantity, Margin off, and Open Orders (0). The separate limit price is no longer populated. This confirms the Market form can be selected; it does not verify trigger/fill behavior, holdings, or protection. No further screenshots of the same blank form are needed.
- Inventory reservation, trigger reference/direction, partial fills, competing-exit cancellation and accepted protective-order status remain unverified. No order was requested by the assistant; this screenshot provides no evidence of an active protective order. No account balance or current market assessment inferred from it.

## Protection documentation and updated scenario — 2026-09-25

- Official OCO documentation (updated August 26, 2026): paired exits reserve one side's cost; triggering one side cancels its counterpart. A triggered limit order may remain unfilled after the other exit is canceled. These semantics apply to OCO, not automatically to independent TP/SL orders. Source: https://www.bybit.com/en/help-center/article/One-Cancels-the-Other-OCO-Orders
- Official Spot Trading Rules (updated July 21, 2026): market orders can partially fill or be canceled under price limits. OHLC alone cannot reconstruct those limits, liquidity or residual inventory. Source: https://www.bybit.com/en/help-center/article/Bybit-Spot-Trading-Rules
- Dedicated standalone spot TP/SL article failed to load twice. Standalone reservation and trigger-reference details remain unverified; no undocumented equivalence to OCO assumed. User screenshots prove selectable forms only. Actual accepted protection and partial-fill handling are still untested.
- New configuration: examples/backtest-current-evidence-20260925.json. Uses observed tick 0.1, quantity precision 0.000001, minimum value 5, and account-displayed fee rates 0.001. Disables deprecated minimum quantity via zero; uses market maximum 120 conservatively for both order types. Retains a local notional cap explicitly labeled as a modeling constraint, not an exchange rule. Quote precision, dynamic price bands and full execution state are not implemented.
- Spread/slippage remain illustrative, and current evidence is not historical verification. Original configuration and report preserved. Same September 1–3 development dataset rerun in report-btc-current-evidence-20260925.json: zero completed trades, net P&L 0 USDT, live_eligible false. This is a configuration check, not fresh validation or evidence of profitability.
- Simulator still assumes full exit fills. Do not use its results to claim verified exchange execution or implement a live OCO workflow. No strategy change, live order, or account action performed.

## Broader collection completed — 2026-09-25

- Development: history-btc-dev-jun-jul-2026.json, June 1–August 1 exclusive, 87,840 one-minute bars; SHA-256 4c8de39beb437219f1eaea301c244cf9871667b56fa8e99b124ca2762e1c65ee.
- Validation: history-btc-validation-sep04-23-2026.json, September 4–23 exclusive, 27,360 one-minute bars; SHA-256 60872daa81ce3a55ba97befbc14b7577a30e3bce5b9ddf6a399bb2fdecb3d50c.
- Both include 800-hour warmup. Full schema, gap/duplicate/count/boundary, OHLC-quality and cross-timeframe checks passed. Evidence: integrity-dev-jun-jul-2026.json and integrity-validation-sep04-23-2026.json. This checks internal consistency, not independent exchange-data authenticity.
- Frozen strategy/tool/config hashes still match evaluation-plan-20260925.json. No signal evaluation or return calculation performed on either broader dataset. No missing candles synthesized, endpoint fallback used, or trades placed.
- October holdout remains future and unavailable. Next: specify/test delayed and incomplete-fill execution stress on development, freeze analysis/uncertainty method, then assess development before opening validation returns. Positive research results alone will not authorize live trading.

## Development stress implementation — 2026-09-25

- Added optional deterministic exit-fill/retry and entry-expiry scenarios to tools/backtest.py; all 44 synthetic tests pass. No live or journal trades created.
- Six scenarios registered before running in development-stress-plan-20260925.json, retaining the earlier plan. Strategy and risk rules unchanged. Broader development outcomes: 20 signals, zero entries in all scenarios, flat simulated 100 USDT. Details: validation.md and development-stress-summary-20260925.json.
- Every signal's next-minute open equals its reference close; adding the assumed spread causes the maximum-entry check to fail. This identifies an entry/quote-model limitation, not an edge. Real-data partial-exit behavior remains untested because there were no entries. Validation outcomes are still unopened; October holdout remains future.

## Forward observer started — 2026-09-28

- Implemented tools/observer.py with local atomic evidence, exclusive process lock, pinned code hashes, one check per hourly close, bounded requests and explicit downtime/late/stale outcomes. 55 tests pass; no strategy or risk-calculator changes.
- Scope is forward quote eligibility, not automatic paper positions or trade-outcome tracking. No fresh account/risk input supplied, so a qualifying quote will be labeled quote_pass_risk_unverified. No current account equity, orders or loss allowances inferred from September 24 confirmations.
- Started local process PID 80788 at 03:32:31 UTC / 04:32:31 Africa/Lagos, with a seven-day limit ending October 5 at 03:32:31 UTC. Process existence and command were verified after launch. Log: observations/tpb-v1/observer-20260928.log; per-hour evidence: observations/tpb-v1/checks/.
- Initial 03:00 UTC boundary was correctly marked missed_check because launch was outside the entry window. First scheduled on-time attempt is 04:00:02 UTC / 05:00:02 Lagos on September 28. Startup public snapshot probe timed out after 25 seconds; successful live observation is not yet established. Hourly failures will be logged, not backfilled.
- Requires this Mac awake and connected. No auto-start, cloud service, notifications or sleep-setting changes. Restart records gaps. This process performs no live orders and opens no paper positions; observe signal/quote feasibility before assuming trade eligibility.
- October observations overlap the planned prospective holdout. Keep trade returns unopened and do not use October observations to select or tune a strategy while claiming October is untouched. Any such use consumes that period; record a replacement holdout before subsequent evaluation.

## Manual trading workflow adopted — 2026-09-28

- User explicitly replaces observer-led research workflow with discretionary six-step market/news/screening/planning/management/review sessions. User executes all trades. AGENTS.md records the scope change while preserving security and capital constraints; TPB-v1 remains unvalidated and is not silently promoted.
- Stopped observer PID 80788 via SIGTERM; verified process absent. Evidence retained. No automatic hourly checks or notifications remain active.
- User answered "yes, 100usdt" to account reconciliation asking about full 100 USDT balance, no open positions/pending orders and no realized losses or daily/weekly halts today/this week. Recorded as user confirmation; no authenticated account query performed. Period-start balances/external flows remain subject to verification if needed for sizing.
- Session research began at 07:54 UTC / 08:54 Africa/Lagos. Fresh BTCUSDT and ETHUSDT snapshot requests both hit their 25-second deadline; no snapshots accepted. No verified current exchange candles, spread, depth or execution levels are available.
- CoinGecko aggregate page showed total market cap 2.93T USD, 24h change -1.51%, BTC dominance 56.96%, but no observation timestamp; contextual website values only, not execution evidence. ETH dominance not verified. Source: https://www.coingecko.com/en/charts . Same-provider HTTPS redirect from /en/global-charts reviewed within passive-text scope.
- Verified calendar: JOLTS September 29 10:00 US Eastern (15:00 Lagos); GDP third estimate and August Personal Income/Outlays September 30 08:30 US Eastern (13:30 Lagos); Employment Situation October 2 08:30 US Eastern (13:30 Lagos). Next scheduled FOMC meeting October 27–28; next CPI October 14. Sources: https://www.bls.gov/schedule/2026/ ; https://www.bea.gov/news/schedule ; https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm . Calendar events are potential volatility catalysts, not directional predictions.
- Current Reuters date-filtered search did not return usable September 28 crypto headlines. ETF flows, unlocks, regulatory and exchange developments are not comprehensively verified; no claim that none exist.
- BTCUSDT/ETHUSDT are initial screening candidates only. Current trend/volatility/liquidity and entry/stop/target prices cannot be validated from these results. Session call: wait for timestamped Bybit 4h/1h charts and current bid/ask; no actionable entry issued, no position size fabricated, no order placed.

## Manual-session improvements approved — 2026-09-28

- User approved the five proposed improvements: defined setups, WAIT/CONDITIONAL/READY decisions, pre-entry trade cards, after-fill protection verification, and setup-specific review including skips.
- AGENTS.md now enforces one position including pending entry exposure, default 0.5% planned risk under existing limits, single-target preference and 2:1 minimum net reward/risk. No capital limit increased; no trade placed or classified READY by this documentation change.
- manual-setups.md defines MPB-v1 trend pullback and MBR-v1 breakout retest. Closed-candle swing/trigger conventions and entry expiry are explicit initial operational choices, not optimized or validated profitability claims. These are separate from TPB-v1.
- manual-trade-card.md is the blank reusable template. Copy completed, uniquely identified revisions here; keep paper/live modes separate and record skips and actual fills honestly. Do not put manual/live results into the TPB-v1 paper-only structured journal.
- Review triggers: rule breach, risk overshoot, costs above the recorded allowance, or protection/partial-fill issues require immediate review and block further affected entries. Nonpositive cumulative expectancy or negative weekly setup P&L triggers a documented weekly review before the next entry; this is a process check, not a statistical verdict. Existing daily/weekly halts still apply. No new numerical capital-loss threshold introduced.

## Manual session — 2026-09-28, 09:12 Africa/Lagos

- User reconfirmed 100 USDT, no positions/pending orders/trades/losses since last confirmation. Account data remains user-reported. Default planned risk 0.50 USDT subject to all limits. No change to fees/risk limits reported.
- Status: **WAIT**. Fresh direct Bybit snapshots succeeded at approximately 08:12:09 UTC / 09:12:09 Lagos. These are timestamped observations, not continuously executable quotes; refresh before any later plan.
- BTCUSDT: bid/ask 82974.2/82974.3; preceding 24 completed hourly candles return -2.16%, high/low 85166.1/82698.2, turnover 472,527,267.04 USDT. Top ask notional 48,826.97 USDT. Snapshot suggests adequate displayed size for this account, not guaranteed execution.
- ETHUSDT: bid/ask 2648.49/2648.5; preceding 24 completed hourly candles return -2.72%, high/low 2724/2635.54, turnover 153,478,076.67 USDT. Top ask notional 9,523.95 USDT. Snapshot suggests adequate displayed size for this account, not guaranteed execution.

- Plan IDs MAN-20260928-BTC-01 and MAN-20260928-ETH-01, revision 1: both WAIT; screen MPB-v1/MBR-v1 spot-long setups. BTC last closed 4h close 82955.1 is below the latest confirmed 4h swing low 83830.4 (September 26 20:00 UTC candle). ETH last confirmed swing lows fell from 2679.34 to 2664.43 and last closed 4h close 2644.22 is below the latter. Both fail mandatory context; no entry/stop/target/quantity assigned. Missing downstream plan fields do not imply READY.
- BTC watch levels: 82698.2 recent 24-hour low; 83830.4 broken confirmed swing low. Reclaim alone is not an entry: reassess closed 4h structure, then require the appropriate premarked-zone hourly trigger, fresh quote and net risk/reward. ETH remains secondary until required swing structure recovers. Next hourly close 09:00 UTC / 10:00 Lagos; next 4h close 12:00 UTC / 13:00 Lagos. No background monitoring active.
- Aggregate context: CoinGecko page displayed BTC dominance roughly 57%, ETH 11%, total market cap down 1.51% in 24h. Timestamp unspecified and header/body values differ slightly; use approximate contextual numbers only, not a dominance trend or execution quote. Source: https://www.coingecko.com/en/charts
- News: Reuters report updated September 28 02:03 EDT / 06:03 UTC describes US-Iran tensions, oil rising and dollar near two-month highs. Source: https://www.marketscreener.com/news/dollar-firms-as-us-iran-tensions-lift-oil-hawkish-fed-bets-build-ce785adcdb89f522 . Interpretation: relevant inflation/risk-appetite pressure and headline volatility, not proof of causality for each crypto move. ETF flows, token unlocks and exchange-specific changes not independently verified; no catalyst trade adopted.
- Scheduled catalysts: JOLTS September 29 15:00 Lagos; GDP revision and August income/outlays/PCE September 30 13:30 Lagos; jobs October 2 13:30 Lagos. Sources: https://www.bls.gov/schedule/2026/ and https://www.bea.gov/news/schedule . Avoid treating scheduled releases as directional predictions.
- Evidence: snapshot-session-btc-20260928-b.json, snapshot-session-eth-20260928-b.json, session-analysis-20260928-b.json. No order placed, no paper fill invented, no short/leveraged alternative proposed. Session remains WAIT based on failed long conditions.
