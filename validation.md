# TPB-v1 validation record

Status: **unvalidated; paper/research only**. June–July development runs found 20 signals and zero entries across six scenarios; no profitability evidence or verified live results exist. September validation outcomes remain unopened. Software tests validate calculations and safeguards, not profitability.

## Experiment register

| Version | Change | Evidence available | Decision |
| --- | --- | --- | --- |
| TPB-v1 | Initial fixed 4h EMA50 / 1h EMA20 pullback-reclaim hypothesis | 44 synthetic tests; June–July development: 20 signals, zero entries across six registered scenarios; prior smoke: one missed signal | Inconclusive; research only |

Keep every tested variation, including failures. Freeze code and dataset hashes before evaluating. Record the actual dated development, validation, and final unused periods before testing; do not choose their boundaries after viewing performance. Separate overlapping trades across splits and include necessary indicator warmup without using future observations.

## Evidence required before proposing live eligibility

1. Auditable, complete dataset of the correct exchange/product, with known candle closure times and execution-data granularity. Sufficient coverage of differing market conditions, not just a favorable recent window.
2. Chronological evaluation on unused data, followed by forward paper observations. Any tuning against a test period requires a new untouched evaluation period. Keep selection/multiple-testing bias visible.
3. Actual or explicitly conservative fees, fee currencies, spread, slippage, gaps, partial/missed fills, minimum sizes, and latency. Stress costs and fills; report whether the apparent edge survives. Apply the account caps and one-position rule in a full simulation.
4. Net expectancy in USDT and R; profit/loss distributions, sample size, uncertainty method and assumptions, peak-to-trough equity drawdown including open positions, losing streaks, and share of profit contributed by the largest winners. Dependent/overlapping trades require dependence-aware uncertainty estimates; do not interpret a handful of trades as independent proof.
5. Cash and buy-and-hold comparisons over the same dates, capital basis, and applicable costs; compare risk/exposure as well as returns. USDT cash carries its own valuation/custody risk.
6. Demonstrated order/stop mechanics and account fee verification. No software test or simulated stop is evidence that a live protective order was accepted.
7. Predeclared strategy suspension/review thresholds, review cadence, and live-promotion decision. Set thresholds from evidence and account constraints before live use, not after a bad result. Broken data, unexpected execution, or violated assumptions immediately suspend new entries.

## Current blockers

- Broader dates and frozen code/config hashes are registered in evaluation-plan-20260925.json. June–July development and September 4–22 validation data collected and integrity-checked; validation signals/returns remain unopened. Performance evaluation and future holdout remain outstanding.
- Broader development evaluation completed with 20 signals and zero entries. No real-data trade outcomes or forward paper outcomes exist.
- Current displayed account Spot fees are evidenced by the user screenshot received 2026-09-24: maker/taker 0.1000% each, Regular User, MNT discount off. Historical fees, actual-fill fee currency, stop support, current pair constraints, pending orders and period halt status remain unconfirmed.
- Subsequent current-pair evidence at 21:11:55 UTC: instrument-btc-20260924.json verifies BTCUSDT Trading status, tick 0.1 USDT, quantity precision 0.000001 BTC, minimum amount 5 USDT, and separate market/limit maximum quantities. Historical constraints remain unknown. The illustrative config's 0.01 tick differs; current field mapping, dynamic price-band checks, and account stop behavior still require implementation/verification before live use. Existing historical reports remain unchanged.
- No trade-return uncertainty estimate is possible from zero trades; strategy suspension thresholds remain outstanding. June–July benchmark results exist but do not establish strategy superiority. Exact uncertainty-analysis protocol must be frozen before validation is opened.
- Earlier DNS failures are preserved in diagnostics-20260924.json and diagnostics-after-cache-flush.json. The retry at 2026-09-24 17:08:35 UTC passed DNS, verified TLS, and the public spot API. See diagnostics-retry-20260924.json. Availability was demonstrated at that time; the original outage cause is unknown.

## First real-data smoke run — 2026-09-24

- Dataset: history-btc-retry-20260924.json, Bybit BTCUSDT spot, September 1 00:00 UTC through September 3 00:00 UTC (exclusive), 2,880 one-minute execution bars plus indicator warmup. SHA-256: `63ad0341514a5e160d8331fa51c757f219d13c67d2de2bfe6a649db99e644224`.
- Report: report-btc-retry-20260924.json; configuration: examples/backtest-assumptions.json (illustrative, unverified costs and instrument rules). Report preserves dataset/config/code hashes.
- One qualifying signal was missed because its modeled opening ask exceeded the maximum entry price. Zero trades; simulated equity stayed at 100 USDT; expectancy and win rate are undefined.
- Same-period full-capital buy-and-hold modeled P&L: -1.94889785191 USDT; cash: 0 USDT. Exposure is not risk-matched. This tiny sample does not establish strategy superiority.
- This is a development/integration check, not an untouched validation period. It demonstrates successful collection and simulator processing, but does not exercise a real-data filled-trade outcome or establish an edge.

## Software verification

Account interface evidence received 2026-09-25: BTC/USDT Spot Sell TP/SL form offers Limit and Market execution, with Margin off. Availability is visually confirmed; trigger semantics, inventory reservation, partial-fill handling, linked-exit cancellation and actual acceptance remain unverified. See trade.md. No live eligibility follows from this screenshot.

A subsequent screenshot confirms Market is selectable in that TP/SL Sell form, with trigger and BTC quantity blank and Open Orders (0). Interface availability verification is complete; documentation and execution-model verification remain outstanding. No order was placed as part of this inspection.

- `python3 -m unittest discover -s tests -v`: 36 tests passed using synthetic fixtures.
- Checked fee-currency inventory math, known-answer sizing, risk/period limits, external-flow accounting, unknown/stale input rejection, quantity/notional restrictions, network endpoint restrictions, redirect refusal, completed candles/gaps, EMA calculation, future-candle isolation, and linked/duplicate/corrected journal outcomes.
- Empty-ledger report contains zero trades and no expectancy estimate; no synthetic test trades are stored in the real journal.
- Live API integration and strategy profitability are not verified by these tests.
- Additional simulator checks cover paginated/gap-checked data, agreement between timeframes, end-to-end signal-to-trade behavior, no chasing, one-position enforcement, stop-first ambiguous bars, gap losses, 12-hour exits, boundary liquidation labeling, Lagos period resets/latched halts, net inventory/fees, cash conservation, benchmarks, and reproducible CLI reports. No synthetic P&L is claimed as market evidence.

Do not automatically promote a strategy at any trade-count or win-rate threshold. Inconclusive or adverse results mean research only, refinement on development data, or rejection—not increased risk.

## Protection documentation and updated scenario — 2026-09-25

- Official OCO documentation (updated August 26, 2026): paired exits reserve one side's cost; triggering one side cancels its counterpart. A triggered limit order may remain unfilled after the other exit is canceled. These semantics apply to OCO, not automatically to independent TP/SL orders. Source: https://www.bybit.com/en/help-center/article/One-Cancels-the-Other-OCO-Orders
- Official Spot Trading Rules (updated July 21, 2026): market orders can partially fill or be canceled under price limits. OHLC alone cannot reconstruct those limits, liquidity or residual inventory. Source: https://www.bybit.com/en/help-center/article/Bybit-Spot-Trading-Rules
- Dedicated standalone spot TP/SL article failed to load twice. Standalone reservation and trigger-reference details remain unverified; no undocumented equivalence to OCO assumed. User screenshots prove selectable forms only. Actual accepted protection and partial-fill handling are still untested.
- New configuration: examples/backtest-current-evidence-20260925.json. Uses observed tick 0.1, quantity precision 0.000001, minimum value 5, and account-displayed fee rates 0.001. Disables deprecated minimum quantity via zero; uses market maximum 120 conservatively for both order types. Retains a local notional cap explicitly labeled as a modeling constraint, not an exchange rule. Quote precision, dynamic price bands and full execution state are not implemented.
- Spread/slippage remain illustrative, and current evidence is not historical verification. Original configuration and report preserved. Same September 1–3 development dataset rerun in report-btc-current-evidence-20260925.json: zero completed trades, net P&L 0 USDT, live_eligible false. This is a configuration check, not fresh validation or evidence of profitability.
- Simulator still assumes full exit fills. Do not use its results to claim verified exchange execution or implement a live OCO workflow. No strategy change, live order, or account action performed.

## Preregistered collection and evaluation plan — 2026-09-25

Plan: evaluation-plan-20260925.json records registration time, frozen strategy/tool/config hashes and scenarios before broader collection.

| Role | UTC start (inclusive) | UTC end (exclusive) | Action |
| --- | --- | --- | --- |
| Development | 2026-06-01 | 2026-08-01 | Collect 61 days; development/model checks allowed |
| Validation | 2026-09-04 | 2026-09-23 | Collect and check integrity only; keep outcomes unopened |
| Prospective final holdout | 2026-10-01 | 2026-11-01 | Future data; collect only after completion |

August was already accessed as indicator warmup and is excluded from fresh evaluation. September 1–3 was used for smoke testing; September 23–25 charts/snapshots were inspected. All indicator warmup is context only, never scored as trades. Dates were chosen for chronology and known exposure, not measured performance. The 61-day development range fits the collector's 90,000-bar bound; calendar coverage does not prove regime diversity.

Baseline uses the current-evidence configuration. Prespecified adverse spread/slippage scenarios are 2x and 4x baseline, with fees unchanged; these are hypothetical stress tests, not measured execution. No strategy parameters or risk limits change. Partial-fill and latency models, plus the exact uncertainty-analysis method, must be specified and tested on development before validation outcomes are opened. This is a staged preregistration, not a claim that those missing models already exist.

Score independent accounts per period with 100 USDT and 800-hour indicator warmup. Never compound independently reset reports. Identify end-boundary liquidations separately. Report all signals/skips, P&L and R after costs, drawdown, streaks, exposure, winner concentration and same-period cash/buy-and-hold comparisons. Too few trades means inconclusive. Failed net expectancy under costs means adverse evidence, not a reason to loosen risk. Any retuning against validation consumes it; final holdout must remain untouched until the complete protocol is frozen. Live eligibility remains false.

## Broader collection completed — 2026-09-25

- Development: history-btc-dev-jun-jul-2026.json, June 1–August 1 exclusive, 87,840 one-minute bars; SHA-256 4c8de39beb437219f1eaea301c244cf9871667b56fa8e99b124ca2762e1c65ee.
- Validation: history-btc-validation-sep04-23-2026.json, September 4–23 exclusive, 27,360 one-minute bars; SHA-256 60872daa81ce3a55ba97befbc14b7577a30e3bce5b9ddf6a399bb2fdecb3d50c.
- Both include 800-hour warmup. Full schema, gap/duplicate/count/boundary, OHLC-quality and cross-timeframe checks passed. Evidence: integrity-dev-jun-jul-2026.json and integrity-validation-sep04-23-2026.json. This checks internal consistency, not independent exchange-data authenticity.
- Frozen strategy/tool/config hashes still match evaluation-plan-20260925.json. No signal evaluation or return calculation performed on either broader dataset. No missing candles synthesized, endpoint fallback used, or trades placed.
- October holdout remains future and unavailable. Next: specify/test delayed and incomplete-fill execution stress on development, freeze analysis/uncertainty method, then assess development before opening validation returns. Positive research results alone will not authorize live trading.

## Execution stress protocol — 2026-09-25, before development outcomes

Development-only amendment: development-stress-plan-20260925.json freezes the revised simulator hash and all six scenario/config hashes before running. TPB-v1 strategy and risk-calculator hashes are unchanged; the original plan is preserved. Baseline, 2x and 4x execution costs, entry expiry at 60 seconds, half exit with next-minute residual retry, and failed exit with five-minute retry are deterministic sensitivity assumptions. Full entry fills and eventual eligible residual fills remain assumptions. No partial-entry or subminute-latency model is claimed. Failed residual orders leave marked inventory rather than fabricated sales. 44 synthetic tests pass, including conservation, fee accounting, minimum-size residuals, persistent exposure, deadline expiry and CLI provenance. Validation outcomes remain unopened.

## Development execution-stress results — 2026-09-25

All six preregistered runs completed on June–July only; summary: development-stress-summary-20260925.json. Full reports retain dataset/config/execution-model/code hashes and equity paths.

| Scenario | Signals | Entries / completed trades | Net P&L (USDT) |
| --- | ---: | ---: | ---: |
| Baseline | 20 | 0 / 0 | 0 |
| Double spread/slippage | 20 | 0 / 0 | 0 |
| Quadruple spread/slippage | 20 | 0 / 0 | 0 |
| 60-second entry delay | 20 | 0 / 0 | 0 |
| Half initial exit fill; retry after 1 minute | 20 | 0 / 0 | 0 |
| Initial exit fails; retry after 5 minutes | 20 | 0 / 0 | 0 |

Baseline rejects all 20 for opening_ask_proxy_above_maximum; the delay case rejects all for entry_window_expired_by_delay. For all 20 signals the next one-minute open exactly equals the signal reference close. Therefore adding the assumed half-spread of 1 basis point makes the proxy ask exceed the frozen maximum. This diagnoses an interaction between the entry rule and the OHLC quote approximation, not proof that actual quotes could never qualify. No spread was reduced or entry rule loosened to manufacture fills.

The flat 100 USDT simulated equity, zero drawdown and zero returns mean no exposure, not robustness or demonstrated profitability. Mean R and win rate are undefined. Partial/failed-exit paths are covered by synthetic tests only; no development trade exercised them. Baseline full-capital buy-and-hold modeled P&L was -14.9639365920 USDT; exposure is not matched, and benchmarks do not receive the latency/failure stresses.

Next research decision: obtain timestamped bid/ask observations to evaluate the original first-actionable-quote entry condition, or register a distinct strategy version with a justified entry rule using development only. Do not change TPB-v1 or inspect the September validation returns simply to obtain trades. Subminute latency, partial entry fills, actual depth/price-band cancellation, OCO operation and a statistically complete validation protocol remain unimplemented/unverified. No live promotion.

## Forward observer started — 2026-09-28

- Implemented tools/observer.py with local atomic evidence, exclusive process lock, pinned code hashes, one check per hourly close, bounded requests and explicit downtime/late/stale outcomes. 55 tests pass; no strategy or risk-calculator changes.
- Scope is forward quote eligibility, not automatic paper positions or trade-outcome tracking. No fresh account/risk input supplied, so a qualifying quote will be labeled quote_pass_risk_unverified. No current account equity, orders or loss allowances inferred from September 24 confirmations.
- Started local process PID 80788 at 03:32:31 UTC / 04:32:31 Africa/Lagos, with a seven-day limit ending October 5 at 03:32:31 UTC. Process existence and command were verified after launch. Log: observations/tpb-v1/observer-20260928.log; per-hour evidence: observations/tpb-v1/checks/.
- Initial 03:00 UTC boundary was correctly marked missed_check because launch was outside the entry window. First scheduled on-time attempt is 04:00:02 UTC / 05:00:02 Lagos on September 28. Startup public snapshot probe timed out after 25 seconds; successful live observation is not yet established. Hourly failures will be logged, not backfilled.
- Requires this Mac awake and connected. No auto-start, cloud service, notifications or sleep-setting changes. Restart records gaps. This process performs no live orders and opens no paper positions; observe signal/quote feasibility before assuming trade eligibility.
- October observations overlap the planned prospective holdout. Keep trade returns unopened and do not use October observations to select or tune a strategy while claiming October is untouched. Any such use consumes that period; record a replacement holdout before subsequent evaluation.

## Active workflow changed — 2026-09-28

User switched to manual discretionary sessions; the TPB-v1 observer was stopped and verified absent. Research records, unopened validation outcomes and limitations remain intact. Manual plans/results must be recorded separately and do not constitute TPB-v1 validation or demonstrated edge. See AGENTS.md and trade.md.

## Manual setup definitions — 2026-09-28

MPB-v1 and MBR-v1 are now documented in manual-setups.md with a reusable manual-trade-card.md. They have no historical or forward performance evidence and are not TPB-v1 revisions. The user-approved discretionary workflow applies; READY means current pre-entry checks pass, not that a profitable edge has been established. Preserve separate paper/live and setup/version results. No research data was evaluated or observer restarted for this documentation change.
