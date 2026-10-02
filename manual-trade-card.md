# Manual trade card — copy into trade.md for each evaluated setup

Blank template, not an entry recommendation. Unknown required fields prevent READY. Preserve previous revisions; actual fills are recorded only from the user's evidence.

## Decision and evidence

- Plan ID / revision:
- Mode: paper / live (select explicitly):
- Status: WAIT / CONDITIONAL / READY (prefix PAPER for FBR-v1):
- Decision time and timezone:
- Exchange / spot pair / setup version:
- Comparison session ID / shadow account (if paper); FBR-v1 is paper only:
- Comparison window ID / common pair and planned start/end / scheduled check time:
- Assessment coverage for each arm: OBSERVED / DATA_MISSING / NOT_ASSESSED:
- Market structure and supporting closed-candle timestamps:
- Level registration time / swing confirmation time / frozen level origin:
- Annotated support/resistance zone boundaries and source:
- Prospective level-selection rationale / alternatives considered / discretionary choices:
- Nearest overhead resistance and basis:
- Current bid / ask / quote timestamp / source / known depth limitations:
- Exchange book timestamp at/after confirmation and no more than 60 seconds before decision (collection time alone is insufficient):
- Catalyst, source, event time and exposure decision:
- Why this setup qualifies; contrary evidence:
- Outstanding checks / reason for waiting, skipping or missing:
- Primary reason code / additional blockers / observation gaps (see validation.md):

## Account and planned risk

- Current equity / available USDT / observation time:
- Open positions / pending orders (must satisfy one-position rule):
- Day/week starting equity, external flows, losses and halt flags:
- Remaining daily / weekly / portfolio risk allowances:
- Default 0.5% risk budget and any tighter binding limit:
- Confirmed maker/taker fees and fee currencies:
- Price tick / quantity increment / minimum value / applicable maxima:

## Entry and exit plan

- Trigger condition, confirming candle and timestamp:
- Actual trigger-observation time, separate from quote receipt or missed-entry time:
- Breakout close / later retest / later confirmation times (FBR-v1: 1h / 1h / 15m):
- Entry order type / allowed range / maximum acceptable price:
- Invalidation condition / initial stop trigger / stop execution type:
- Target price and structural reason (before identified resistance):
- Maximum holding time / time-exit action:
- Plan expiry and cancellation conditions:
- Management rules, including any explicitly planned partial exit:
- Fees / spread / adverse slippage assumptions and rationale (count once):
- Gross buy quantity / estimated net sellable quantity / dust:
- Cash needed including applicable entry fees:
- Estimated net stop proceeds:
- Planned loss = cash spent minus estimated net stop proceeds:
- Estimated net target proceeds / net reward / net reward-to-risk:
- Protective-order submission method and failure/partial-fill contingency:
- All pre-entry checks satisfied? Evidence and remaining limitations:

## Paper outcome — separate from user execution

- Shadow account / entry observation time / observed quote and assumed fill:
- Manual-ledger entry/event IDs and evidence references:
- Fees, spread and slippage charged; base and stressed assumptions:
- Net inventory, open exposure and day/week halt state:
- Exit observation or fully post-entry candle evidence / ambiguity or data gaps:
- Modeled exit reason, time and price / delayed-management disclosure:
- Net USDT / original planned R / drawdown / adherence / review decision:
- Exposure classification: open / open-or-flat / proven flat under declared fill model:
- Result classification: resolved / bounded uncertain / unknown / missed:
- Possible chronological exit paths / net-proceeds and P&L lower/upper bounds:
- Latest uncertain assessment ID / new reconciliation evidence and reason / superseded paths:
- Conservative cash/equity available for next sizing / retained day/week halt flags:

Do not populate the live-fill section from this model. Missing evidence remains unresolved, not a profitable hypothetical fill.

## After user execution — do not prefill

- Actual entry fills: time, price, quantity, fee amount/currency:
- Reconciled cash spent / net sellable inventory:
- Accepted stop quantity, trigger, execution type and confirmation:
- Target order state / linked cancellation or inventory reservation behavior:
- Unexpected costs, partial fills, protection issues and response:
- Management changes with timestamp and reason:
- Exit fills: time, price, quantity, fee amount/currency:
- Net P&L in USDT / R relative to original planned risk:
- Planned versus actual costs / rule adherence / lesson:
- Review required? Reason, corrective action and recorded resumption decision:
