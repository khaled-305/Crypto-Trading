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
- Pending execution details: quote currency, actual fee tier, and supported stop/order types.

## Session — 2026-09-24, 12:12 Africa/Lagos

- Status: research only; no entry recommended or order placed. Actual account positions and P&L remain unconfirmed.
- Bybit BTC/USDT spot snapshot at 11:11:53 UTC (12:11:53 Lagos): last 83,529.1 USDT; 24-hour change -2.58%; range 82,858–85,946.9; turnover approximately 609.18 million USDT; best bid/ask 83,529.1/83,529.2. This is a snapshot, not a streaming feed or full order book. Source: https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT
- CoinGecko aggregate snapshot at 11:04:19 UTC: BTC dominance 59.24%, ETH 11.42%; market capitalization change -6.32% over 24 hours; reported volume approximately $119.25 billion. A single snapshot does not establish a dominance trend. Source: https://api.coingecko.com/api/v3/global
- BEA calendar: international transactions/investment position release September 24; GDP and personal income/outlays September 30. Source: https://www.bea.gov/news/schedule
- BTC/USDT is a watch candidate only. Candle retrieval failed; ETH/SOL quotes were unavailable. No validated entry, stop, target, or position size. No historical/paper-test evidence has been supplied for a live-eligible setup.
- Await account reconciliation, actual fees, supported stop types, and current BTC/USDT 4-hour/1-hour chart data and bid/ask before building a conditional paper plan. Do not infer remaining loss allowances from initial capital alone.
