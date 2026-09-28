# Research tools

All tools run locally with Python 3.11+ and its standard library; no installation or API keys are needed. Run commands from this project directory. Nothing places orders or confers live eligibility. Security scope is recorded in security-review.md.

## Workflow

1. Read strategy.md and validation.md. The initial strategy is an untested hypothesis.
2. Collect a fresh public snapshot into a new filename:

```sh
python3 -m tools.market --symbol BTCUSDT --out snapshot.json
python3 -m tools.strategy snapshot.json --out signals.json
```

Both commands refuse to overwrite output. Use a new filename for each observation. A collection failure means unavailable data, not permission to reuse an old snapshot as live. Collector requests up to 1,000 recent candles per timeframe, sufficient for a research scan but not a complete historical validation. Signals are not orders, fills, or P&L. Record every qualifying signal and why it was traded, skipped, or missed.

3. Copy examples/risk-input.json to a local working file. Fill the null fields from current, reconciled account data and current exchange instrument constraints; the template deliberately fails until completed. All monetary values are USDT, rates are decimal fractions (0.001 means 0.1%), timestamps include timezone. Do not put API keys in any input.

```sh
python3 -m tools.risk risk-input.local.json
```

The calculator supports one spot-long entry and one full exit, base- or quote-denominated buy fees, and quote-denominated sell fees. Other fee models or scaled exits require separate implementation/verification. Enter the ask as entry reference; adverse slippage is added once. Stop/target reference prices must align to ticks. The reported sell quantity excludes base fees and rounds down; remaining dust is valued at zero for conservative sizing. Update entry/exit maximums from current instrument rules; use the tighter applicable buy/sell cap. It does not infer account fees, verify account facts, or persist/reset daily/weekly halt flags. Those must be reconciled from the account/session record; unknown inputs are rejected.

4. Append paper signal events as JSON. Example structure (illustrative values, not a real trade):

```json
{"type":"signal","mode":"paper","strategy":"TPB-v1","symbol":"BTCUSDT","timestamp":"2026-09-24T12:00:00+00:00","decision":"skip","reason":"Entry window expired"}
```

```sh
python3 -m tools.journal append --event event.local.json
python3 -m tools.journal report
```

For a `paper` signal decision, also supply `initial_risk_usdt`, `entry`, `stop`, `target`, `quantity`, and `estimated_cost_usdt`. Include snapshot hash, actual observation time, and assumptions as additional fields. The ledger assigns an ID. To close a paper trade, append an `outcome` referencing its `signal_id`, with the same mode/strategy/symbol, exit `timestamp`, `reason`, `exit_price`, `net_pnl_usdt` after all costs, and `observed_cost_usdt`. These remain modeled outcomes, not exchange fills. The ledger validates links, prevents duplicate closes, and preserves events; it cannot independently verify manually supplied P&L.

The report describes closed paper trades only. It does not estimate intratrade drawdown, statistical confidence, benchmark returns, or profitability. Those must be produced and recorded in validation.md before any live proposal. Never mix historical simulations, paper observations, and actual live trades in one performance series.

To correct an event, append a `void` event with `voids_id`, `timestamp`, `reason`, and the same mode/strategy/symbol, then append the corrected event. Original rows remain in the audit trail. Void a linked outcome before voiding its signal. Reports exclude voided events. This append-only workflow is not a tamper-proof database; retain backups and do not edit the ledger directly.

## Verification

```sh
python3 -m unittest discover -s tests -v
```

Tests use synthetic fixtures, do not contact an exchange, and do not create real journal trades. They verify risk/fee calculations, rejection behavior, candle handling, absence of future-candle influence, and journal consistency.

## Diagnose data access

```sh
python3 -m tools.diagnose --out diagnostics-new.json
```

The checker stops at the first failed stage: DNS, certificate-verified TLS, then a public spot API request. It never changes network settings and does not need API keys. Use a new output filename each time.

The recorded check in diagnostics-20260924.json stalled at DNS. No proxy was configured. The user confirmed the browser error `DNS_PROBE_FINISHED_NXDOMAIN`. A local `dscacheutil -flushcache` completed successfully, no matching hosts-file override was found, and diagnostics-after-cache-flush.json still stalled at DNS. This does not establish a geographic restriction or a Bybit account problem. Bybit's official integration guide still lists `api.bybit.com` as a mainnet endpoint: https://bybit-exchange.github.io/docs/v5/guide.

- DNS failure/timeout: investigate resolution and permitted access to `api.bybit.com` on the current device/network with the network administrator or ISP. If the browser also fails, changes to Python query parameters will not solve it.
- To localize the fault, compare the same public URL in a phone browser on mobile data versus the affected Wi-Fi. This is a diagnostic comparison, not authorization to evade an access restriction. If one resolves and the other does not, report that difference and the NXDOMAIN error to the relevant network administrator/ISP. If neither resolves, ask Bybit support to confirm the endpoint and service availability for your account/location. Do not assume which provider is responsible from NXDOMAIN alone.
- Browser succeeds but Python fails: inspect the staged result and local application/network policy. Do not disable TLS or silently use a different proxy/provider.
- TLS failure: check device clock and the trusted certificate/network configuration; do not turn off certificate verification.
- HTTP 403: stop and confirm the cause and permitted service access with Bybit/network support. Do not use a VPN or alternate hostname to bypass a restriction.
- HTTP 429: stop repeated requests and respect exchange limits.

Retry update, 2026-09-24 17:08:35 UTC: diagnostics-retry-20260924.json passed DNS, verified TLS, and the public spot API without changing network settings or endpoints. The original outage cause remains unknown. Historical collection then succeeded; report-btc-retry-20260924.json records a September 1–3 smoke run with 2,880 one-minute bars, one missed signal and zero trades. See validation.md for the evidence and limitations. Recheck availability before a large download if failures recur.

## Download historical research data

After the diagnostic passes, this example collects two days for an exploratory smoke run plus 800 hours of indicator warmup. These are example development dates, not a preregistered validation split or evidence of profitability.

```sh
python3 -m tools.history --start 2026-09-01T00:00:00Z --end 2026-09-03T00:00:00Z --out history-btc-sep01-03.json
```

Use UTC 4-hour-aligned boundaries and an exclusive end time. The default execution interval is one minute; `--execution-interval 60` is a coarser approximation. Neither interval supplies real bid/ask, order-book depth, fill latency, or queue position. Do not claim that even one-minute OHLC proves execution within the real 60-second entry window.

The downloader uses reviewed public Bybit spot endpoints, paginates explicitly, retains response URL/timestamp/hashes, and rejects gaps or duplicate/out-of-range candles. No missing bars are fabricated. Each network request has a 15-second process deadline and stops on failure; no credential or regional-host fallback is attempted. A file covers at most 90,000 execution bars. For longer research, plan dated chunks and preserve the full warmup and evaluation history; do not average separate-reset runs as if they were a continuous account simulation.

The schema-2 JSON contains `kind: bybit_spot_ohlcv`, `category: spot`, `symbol: BTCUSDT`, `evaluation_start_ms`, `evaluation_end_ms`, `warmup_start_ms`, `execution_interval_minutes`, and arrays `h1`, `h4`, and `execution`. Each row is `[start_ms, open, high, low, close, volume, turnover]`. Timeframes must agree in overlapping OHLC values. The simulator can read an existing local file in this schema, but provenance/security of any independently supplied dataset must be reviewed first. A hash only identifies content; it does not prove it is authentic exchange data.

## Run the historical simulator

```sh
python3 -m tools.backtest history-btc-sep01-03.json --config examples/backtest-assumptions.json --out report-btc-sep01-03.json
```

The example configuration contains explicit **illustrative fees and instrument restrictions**, not verified account or historical values. Copy it to a local JSON file and replace the assumptions with dated evidence for serious research. Keep each tested configuration/version; never silently rewrite the assumptions behind an existing report. The tool accepts only `purpose: exploratory` and always reports `live_eligible: false`.

The simulator uses TPB-v1 signals and the tested sizing function. It models one position at a time, missed opening quotes, fees in the correct currency, tick/quantity rounding and dust, stops, targets, 12-hour exits, and Lagos daily/weekly halts. A gap may exceed planned risk. If stop and target are touched in the same bar, stop wins. Targets are modeled full exits with adverse execution costs—not confirmed limit fills. The entry assumes the execution bar's open was actionable; real latency may invalidate that assumption. Spread is a full bid/ask fraction; half the spread plus slippage is modeled as adverse cost on each side, without adding it twice.

Signals blocked by another position or a risk/order constraint are recorded with a reason. Historical decisions and trades are saved only in the report, not in the paper/live ledger. Initial account equity is a synthetic flat account at the start of the evaluation, including starting day/week budgets; it is not evidence of the user's actual account history.

Reports include net equity/P&L, R-multiples for completed strategy trades, modeled intrabar drawdown, halted periods, skipped signals, cash/buy-and-hold comparisons, supplied assumptions, and dataset/config/code hashes. A forced liquidation at dataset end affects equity but is separately labeled and excluded from ordinary completed-trade averages. Buy-and-hold uses full capital and is not risk-matched to the strategy. Intrabar drawdown is an OHLC-path model, not measured tick-by-tick drawdown.

The simulator does not yet establish statistically significant expectancy, control selection bias, reconstruct historical exchange rule changes, or verify mainnet execution. Complete validation.md with suitable real data, frozen chronological evaluation periods, cost stress scenarios, and forward paper evidence before any live proposal.

## Current-evidence scenario (2026-09-25)

Use examples/backtest-current-evidence-20260925.json for a separately labeled exploratory scenario incorporating the observed current tick and displayed fees. It retains illustrative spread/slippage and a local notional cap; it does not verify historical constraints or replicate exchange order handling. Original examples and reports are preserved. See validation.md for OCO trigger-cancellation and market partial-fill limitations and the zero-trade rerun.

## Optional deterministic execution stress

The simulator accepts `--execution-model examples/stress-half_exit_retry_1m-execution.json` alongside the usual dataset/config/out arguments. Example:

```sh
python3 -m tools.backtest history-btc-dev-jun-jul-2026.json --config examples/stress-half_exit_retry_1m-config.json --execution-model examples/stress-half_exit_retry_1m-execution.json --out report-half-exit-new.json
```

Use a new output filename. The three required model fields are `entry_delay_ms` (0 or 60000), `exit_first_fill_fraction` (0 through 1), and `residual_retry_delay_bars` (integer 1 through 60). These scenarios require one-minute execution candles. Delay of 60000 expires the entry; subminute delays are rejected because no corresponding quotes exist in OHLC. First-fill fraction is applied once at the first exit attempt; residual inventory is retried at a later bar open with adverse costs. Partial entries are not modeled.

A newly submitted residual order must meet size/value restrictions. If it cannot, inventory stays exposed and subsequent retries may fail. End-of-data does not magically clear a pending residual. Reports include remaining inventory, ending cash, marked equity, realized partial proceeds, and each hypothetical exit attempt (including zero-quantity failures). Total P&L includes unresolved inventory at last close, before future exit fees; completed-trade averages exclude unfinished positions. Baseline full-fill behavior is retained when no execution model is supplied. These stress assumptions do not reconstruct exchange depth, queueing, cancellation, or OCO mechanics.

The six development scenarios and exact hashes are recorded in development-stress-plan-20260925.json; results in development-stress-summary-20260925.json. All produced zero entries, so only synthetic tests exercise partial/failed-exit paths. Validation outcomes must stay unopened pending the next documented research decision and complete evaluation protocol.

## Forward quote observation — TPB-v1

`python3 -m tools.observer --directory observations/tpb-v1 --hours 168` runs for at most seven days. `--once` performs one current-hour check; `--report` summarizes existing records without network access. Two seconds after each UTC hourly close (minute 00 in Lagos), the observer requests completed candles/current instrument rules. For a qualifying signal it then requests exactly one fresh book, recording source payloads, timestamps and code hashes. It rejects quotes over two seconds old, future/pre-close quotes, and observations outside the 60-second window. It never searches later quotes to rescue a failed entry. The initial snapshot book is not reused as an actionable post-signal quote.

This phase answers whether actual observed asks satisfy the frozen maximum price. It does **not** open paper positions, simulate fills, track stop/target outcomes, or place live orders. Passing quotes are `quote_pass_risk_unverified` by default. Optional `--risk-input` accepts a fresh local paper input matching examples/risk-input.json; it checks current tick/quantity/minimum/maximum restrictions and invokes the risk calculator. A math pass is still not an executable setup: depth, latency, protection and other execution constraints remain unverified. Account data is never sent to Bybit.

Each check is atomically published once under `observations/tpb-v1/checks/`; files are not overwritten. Runs and pinned code hashes are under `runs/`. A lock prevents two observers using the same directory. Late startup and downtime are recorded as missed checks, never backfilled with hypothetical quotes. A running process stops if its code changes. Candle snapshots retain the exact rolling EMA initialization history; signals can depend on that seed. No claim of a common historical EMA seed is made.

The Mac must stay awake with network access. There is no launch-at-login service, sleep prevention, cloud deployment or notification service. On sleep/wake, later checks record missing boundaries; to recover after process exit, rerun the command. Stop an interactive run with Ctrl-C; for a detached run, verify its PID from the run record and terminate that specific process. Observations are local and excluded from git.

Review with `python3 -m tools.observer --directory observations/tpb-v1 --report`. Review coverage first, then signals, quote rejections and price-rule passes. No-signal, missed-window and data-unavailable are distinct. Zero trades is expected because this observer records eligibility evidence only; it must not be represented as a trading-performance test.
