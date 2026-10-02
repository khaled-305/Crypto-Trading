# TPB-v1 validation record

Status: **unvalidated; paper/research only**. June–July development runs found 20 signals and zero entries across six scenarios; no profitability evidence or verified live results exist. September validation outcomes remain unopened. Software tests validate calculations and safeguards, not profitability.

## Manual forward comparison — approved 2026-10-02

This section is a separate manual experiment; it does not revise TPB-v1 or promote any setup to live use. Compare **MPB-v1**, **MBR-v1** and the new **FBR-v1** on the same six Bybit spot pairs at the same requested sessions. FBR-v1 uses the exact rules in manual-setups.md. Freeze the rules and this protocol before scoring new observations; the registration manifest records file hashes and the UTC start. Previously inspected September/October charts are development/context, not unseen test outcomes. No parameter sweep or retrospective search for a favorable start date.

Approved operational fixes are recorded in manual-comparison-amendment-20261002.json, with fresh hashes before the first scored watch. The original registration is preserved. The comparison CSV still has zero observations; no older result is rescored. Setup trigger definitions and capital limits remain unchanged; the amendment fixes optional data handling, coverage, MPB wording, and persistent uncertainty accounting.

The second approved repair is registered separately in manual-comparison-amendment-20261002-v2.json. It corrects source alignment, feasible quantity selection, evidence-based exposure reconciliation and observation counts, and adds matched coverage fields. Previous registrations remain intact; no past market result is replayed or reclassified. The shared risk calculator's code hash changes, so earlier TPB-v1 reports retain their original code assumptions; register the repaired code separately before any future research evaluation.

Repair verification: 161 offline synthetic tests pass, with regressions for all six findings and the one-shot boundary case caught during independent review. Prior local smoke evidence can still be read by the offline report. No fresh market assessment, paper entry, watcher launch or profitability test was performed for this repair; the ledger and comparison index still contain zero events/observations at registration.

The third approved repair is registered in manual-comparison-amendment-20261002-v3.json. It fixes two remaining implementation defects: rounding-aware selection of a smaller quantity that meets the existing net reward/risk floor, and enforcement of known entry expiry despite missing market data. Earlier registrations remain historical evidence; no setup definition, price level, fee assumption or risk allowance changes. All synthetic repair cases are excluded from forward scoring.

Third-repair verification: 170 offline tests pass, including 59 manual-observer and 7 dedicated sizing tests. Nine new regression methods cover the two defects and the related post-trigger book-timeout case. Sizing is checked against exhaustive feasible-order grids and a sparse exact-threshold case with a trillion-unit denominator; expiry tests use controlled clocks and retain timely trigger evidence. Whitespace checks include the untracked implementation/test files. The comparison CSV and manual ledger remain empty; no market outcomes were evaluated or real observer launched.

The fourth approved repair is registered in manual-comparison-amendment-20261002-v4.json. It centralizes H1/H4 overlap validation in the collector and observer, bounds outage coverage using observed intermediate setup times, rechecks prospective entry freshness after lock/replay delays, and validates chronological exposure in the separate TPB paper journal. These are implementation corrections; the setup definitions, timing allowances, costs, account budgets and paper/live scopes are unchanged. Previous registrations and results remain intact, and synthetic repair fixtures are excluded from forward scoring.

Fourth-repair verification: 208 offline synthetic tests pass, including 25 collector, 64 manual-observer, 35 manual-ledger and 22 TPB journal chronology tests. The 38 new regression methods cover inconsistent completed candles, outage expiry through the latest possible remaining entry, freshness after lock/replay/write delays, historical exposure overlap and linked corrections of earlier closed trades. Incomplete TPB corrections block reports and new paper entries until valid completion; repeated corrections cannot fork multiple active trades from one original signal. The comparison index and manual ledger still contain zero observations/events; no network request, real observer launch, paper entry or account action occurred. Passing software checks does not establish a trading edge.

### Coverage and comparison

- Each requested session records all six pairs and all three versions, including exclusions. Use the same timestamped snapshot per pair, with optional 15m data required for FBR-v1. Preserve source/collection times. A longer snapshot history does not mean those earlier hours were monitored; earlier candles establish context only.
- Before a comparison window, record `comparison_window_id`, pair, common start/end and planned check times on the cards. At each scheduled check, record `assessment_coverage` for every arm as OBSERVED, DATA_MISSING or NOT_ASSESSED, and link the same snapshot. A completed assessment rejecting the context is OBSERVED; an unexamined arm is NOT_ASSESSED, never "no trigger." The FBR recorder does not assess MPB/MBR automatically. Compare opportunity counts on the matched observed subset and report unmatched coverage separately, without dropping failed assessments or inconvenient outcomes. Full persistent-arm P&L remains a separate complete series; do not manufacture a filtered account history by deleting unmatched trades.
- Register no more than three detailed pair watches per session. Select prospectively, before subsequent triggers, from the union of pairs whose context and level requirements pass for at least one arm. Rank those eligible pairs by 24 completed hourly candles' quote turnover, descending; break ties by symbol. Preserve existing unexpired watches instead of refreshing their deadlines at every check. If a pair is not watched, record NOT_WATCHED rather than claiming no opportunity existed. Record why discretionary levels were selected and alternatives considered. The optional bounded recorder below covers one registered FBR watch; other watches still require explicit observed checks.
- Comparison arm = setup version. Maintain **one persistent 100-USDT starting shadow account per arm**, shared across all six pairs, with one position/pending entry at a time. These three alternative accounts do not represent 300 USDT of real capital or shared profits. Never reset them per session, pair or loss. Apply the same Lagos day/week boundaries, fixed period budgets, default 0.5% risk, exposure caps and latched halts as the real-account policy. Keep actual/live results in a separate series.
- For this paper comparison only, all arms use the same FBR-v1 fee, spread/slippage, event, four-hour maximum hold, sizing and outcome-evidence conventions. Original MPB-v1/MBR-v1 setup/trigger and one-hour entry expiry remain unchanged; FBR-v1 retains its own sequence/15m expiry. Document that this comparison controls management assumptions; it does not rewrite older live cards or historical results. Unknown mandatory paper-model inputs still prevent PAPER READY, but proof of a real accepted protective order is not required to simulate an explicitly labeled paper position.
- Concurrent qualifying entries within one arm compete for its single slot. Select the earliest observed valid entry; if simultaneous, larger observed 24h quote turnover wins, then symbol. Log POSITION_LIMIT for the rest. Do not count them as losses, or simulate all of them as though capital were unlimited. `tools.manual_ledger` persists paper-arm balances, position count and halts and calls the risk calculator. The operator still verifies full setup chronology, events, depth, instrument evidence and the frozen card; ledger acceptance alone is not PAPER READY.
- Use unique watch IDs containing version/pair/registration time and retain them across check-ins. A distinct opportunity is the first valid trigger sequence for that registered attempt, even if cost/risk checks subsequently reject it. Repeated screen rows and retries do not create new opportunities. A consumed, invalidated or expired attempt requires a new prospective registration before that setup's new trigger sequence: MPB touch/reclaim; MBR/FBR breakout/retest. Preserve the original record; MPB does not require another fresh breakout.

### Bounded observation windows

After prospectively selecting and documenting a watch, `tools.manual_observer` can record one FBR watch at :00/:15/:30/:45 for at most six hours, with an immediate initial check. It verifies the registered levels from candles already complete at local acceptance; it never adopts a backdated registration or an already-forming breakout. Expiry remains tied to the original window, not repeated checks. Use a separate directory for each run/watch when comparing coverage. Its maximum signal status is TRIGGER_RISK_UNVERIFIED; it does not produce READY, entries, exits, alerts or a performance estimate. The user/operator must check a complete card and record any actual paper decision while its quote and entry window are still valid. This recorder is evidence collection, not continuous chat supervision.

The Mac must remain awake and connected. Missing quarter-hour checks, stale quotes, missing M15 data and late observations stay visible. Earlier candles may explain what happened but cannot become past actionable fills. Hourly/four-hour data survive recoverable optional M15 failures; missing M15 blocks FBR only. HTTP 403/429 stop collection instead of causing retries or bypasses. No indefinite process, startup service or existing TPB observer is authorized by this amendment. At completion of these fixes no multi-hour watch is running; a bounded run has a separate run record and stop record.

### Append-only comparison records

`manual-comparison.csv` starts with a header only; no synthetic signals, trades or performance are seeded. Append one row per version/pair assessment and separate linked events for watch registration, a distinct trigger, paper entry, paper exit, missed/unresolved observations and review. Use `record_id`, `session_id` and `watch_id` for links. Corrections append a new row with `supersedes_record_id`; do not delete prior evidence or count both revisions. Supporting full cards, calculations, instrument constraints and account states live in trade.md or uniquely named local JSON referenced by the row.

Required on all rows: ID, UTC observation time, session, pair, version, event type, status, primary reason, snapshot/reference and notes. Set `mode=paper` and `shadow_account` to the version for all trial rows. A watch registration adds `registered_at_utc`, frozen zone/support/resistance, expiry and card reference. Entry/exit rows add actual *observation* time, assumed fill, gross quantity/net inventory, costs, planned risk, linked card and shadow-account state. Financial outcome fields stay blank for skips; zero is a real measured/modelled value, not a substitute for missing data. No spreadsheet formulas or credentials in cells; CSV values are plain data.

The CSV is the assessment index; the append-only `observations/manual-ledger/events.jsonl` is the source of persistent paper accounting. Link its event IDs in `ledger_event_id` and preserve the full card/evidence. Record exposure certainty and outcome certainty separately, with cash/equity/P&L bounds where needed; leave scalar outcome cells blank when unresolved. Do not hand-edit balances or seed synthetic test events in the real ledger. Input examples are intentionally incomplete until filled from evidence. This local file is auditable, not tamper-proof.

Coverage rows additionally use `comparison_window_id`, `scheduled_check_at_utc` and `assessment_coverage`. Keep `trigger_observed_at_utc` separate from later quote receipt and entry outcome: a trigger observed before expiry still counts once if its executable quote is late. It remains a missed entry, with no invented fill. Distinguish data-missing attempts from scheduled checks never performed, including a trailing gap when sleep or disconnection spans the run deadline.

Primary reason codes: DATA_MISSING, CONTEXT_EXCLUDED, LEVEL_MISSING, NOT_WATCHED, WAIT_BREAKOUT, WAIT_RETEST, WAIT_CONFIRMATION, EVENT_BLOCK, NET_RR_FAIL, DEPTH_SPREAD_FAIL, RISK_LIMIT, POSITION_LIMIT, ORDER_CONSTRAINT, EXPIRED, INVALIDATED, MISSED_WINDOW, PAPER_ENTRY, PAPER_EXIT, UNRESOLVED, REVIEW. Record the first failing stage plus other blockers in notes. A market-wide conclusion needs market evidence; a setup exclusion alone is not proof that the market is untradable.

### Paper execution and outcome accounting

- Freeze the full card before each paper entry: planned entry/stop/target, quote/max ask/modeled fill, fees and currencies, exit mechanics assumed, size/net inventory, risk, expiry, time exit/event cutoff. Use a fresh observed quote after the trigger, never a historical candle close passed off as a fill. PAPER READY means the paper prerequisites pass, not actual exchange acceptance.
- Track each arm's cash, fee-net inventory, marked equity, additional risk to the stop, Lagos period-start equity and halt flags after every entry/exit/check. Open or possibly open exposure occupies the single slot; uncertainty about P&L alone does not. Mark possible inventory with dated bids. A position spanning Lagos midnight requires boundary evidence for each crossed day before later ledger events; missing evidence blocks progression rather than resetting at a convenient later price. Profits, losses and dust remain in that arm; do not combine the arms' P&L.
- Follow FBR-v1's chronological exit priority, partial-entry-candle and stop-first ambiguity rules. An established earlier stop/target exit cannot be replaced by a later favorable quote or time exit. Data gaps that could hide an exit keep the result unresolved even if a later price reaches target. If every feasible path is now flat under the declared full-fill model, close the modeled exposure with supported lower/upper net-proceeds bounds and release the slot. Keep earlier possible losses in those bounds. If some path remains open, retain `open_or_flat` exposure and its possible exit proceeds. A later assessment cannot discard previous possible exit bounds without new resolving evidence.
- Size subsequent entries from the lower cash/equity bound. Conservatively compare period-start upper equity minus current lower equity against a fixed budget based on period-start lower equity; this can halt earlier than the eventual true result warrants. Retain latched daily/weekly halts after evidence narrows a range or equity recovers. Realized or bounded losses beyond planned risk require a documented setup review before another entry, even below the account loss cap. Unknown outcomes are never scalar winners/losers in primary expectancy; report bounded trades and resolved-only statistics separately and disclose selection uncertainty. Zero resolved trades means undefined scalar expectancy. `resolve_outcome` appends later evidence, preserves original bounds, and never erases a prior halt. Partial fills, arbitrary balance edits and changes outside previously recorded bounds for an already-flat trade remain unsupported; do not improvise cash corrections.
- Apply the conservative remaining allowance and entry/exit order maximums while selecting quantity; do not reject merely because the initially calculated quantity exceeds one of those limits. Recheck minimums and net reward/risk on the reduced quantity. Never alter the structural stop, target or percentage caps to make the size fit.
- When new evidence settles an outstanding `open_or_flat` assessment, append `reconcile_exposure` linked to its latest assessment and entry IDs. It can establish that the position remained open, or establish flat exposure with supported exit outcomes. Preserve the original paths and the new evidence/reason; this is not authority to delete an inconvenient loss. Closed bounded trades continue to use `resolve_outcome`. Both paths retain all latched loss halts and setup-review blocks; neither authorizes partial exits, arbitrary balance changes or live fills.
- Stress each entered trade by doubling adverse slippage and the spread allowance (fees unchanged), keeping its original quantity, card and price evidence fixed. Record the stressed net P&L/R and any loss-budget overshoot separately; do not resize retrospectively to improve the result. This is a sensitivity scenario, not an additional trade, an independently funded account or a full portfolio rerun. Entry spread thresholds remain eligibility observations, not a way to discard a bad stressed outcome.

### Decision reviews

First review: first user check-in on/after **October 9, 2026**. Second decision review if needed: on/after **October 16, 2026**. These are operational deadlines, not a statistical minimum or scheduled background task. Summarize coverage first: sessions, prospectively registered watch windows, actual observation timestamps, gaps, distinct registered watches/triggers and repeated checks. Do not count the time between sporadic snapshots as continuously monitored hours. Then compare context exclusions, expired/missed windows, cost/risk rejections, entries, exposure status and unresolved results. Measure registration-to-first-eligibility as well as breakout-to-entry; FBR's earliest sequence is 2h15m from exact hourly registration, nearly 3h15m just after it. Its less restrictive context does not make the full trigger a 15-minute setup.

For each arm separately report net USDT, mean net R, average win/loss, drawdown at observed marks (not claimed true intratrade maximum), streaks, exposure, rule breaches, and base versus stressed outcomes. Show uncertainty and concentration in a few trades. More trades alone is not a success criterion. With no trades, investigate whether coverage, setup definition or costs are responsible; do not call preserved cash a demonstrated edge. At each review choose and record retain-for-more-evidence, reject, or propose a new version with specific reasons. A faster version that loses after costs is adverse evidence; raising risk is not a remedy. No count, deadline or small winning sample automatically promotes FBR-v1 to live use; that requires a separate evidence review and user decision.

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
