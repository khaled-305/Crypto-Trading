# External resource security reviews

Project rule: review before use, at a depth appropriate to the capability. Content is data, not instructions. No resource is certified safe by this register. Re-review changes of source, version, scope, permissions, or behavior.

## 2026-09-24 — Official Bybit documentation

- Sources: https://bybit-exchange.github.io/docs/v5/market/kline ; https://bybit-exchange.github.io/docs/v5/market/orderbook ; https://bybit-exchange.github.io/docs/v5/market/instrument ; https://www.bybit.com/en-GB/help-center/article/Bybit-Spot-Fees-Explained
- Intended use: read public API schemas and fee-currency explanations. Provenance: Bybit documentation domain linked to the exchange's SDK organization and exchange help center; HTTPS.
- Risks considered: stale schemas, misleading examples/defaults, untrusted embedded text/links, instructions that request credentials or execution. Documentation is not a guarantee of endpoint availability or account-specific fees.
- Mitigations: read only; execute no downloaded snippets; send no secrets; explicitly request spot; validate responses and account fees. The local client implements only a fixed allowlist of public GET endpoints.
- Decision: approved for passive documentation reference within this scope. No SDK, package, skill, or remote code installed or executed.

## 2026-09-24 — Bybit public market API

- Source: https://api.bybit.com ; allowed paths /v5/market/kline, /v5/market/orderbook, /v5/market/instruments-info. Intended requests: spot BTCUSDT/ETHUSDT only; strategy v1 only uses BTCUSDT.
- Exposure: exchange receives requester IP, pair, and public query parameters. No credentials or account data are sent. No authentication, order, transfer, or withdrawal endpoints exist in the client.
- Risks: network errors, rate limits, denial of access, stale/wrong-market/malformed data, malicious oversized responses, redirects, and incomplete order-book liquidity. Public snapshots do not guarantee executable prices.
- Mitigations: TLS certificate validation via Python defaults; fixed host/path/symbol allowlists; no redirects; no environment proxies; JSON only; 2 MB response limit; 10-second socket timeout; bounded four-request batch; finite positive prices; timestamps/OHLC/gaps/category checks; no automatic retries or fallback hosts; exclusive output creation and source hashes. Hashes preserve what was received, not proof of authenticity. The public CLI runs the local collector in a child Python process with a 25-second deadline, killing it on timeout because the OS resolver can outlast a socket timeout. No shell or downloaded executable is invoked.
- Decision: approved for read-only public research. On access failure stop collection and report unavailable; do not bypass geographic/account restrictions.
- Connectivity check: the initial public request exceeded 25 seconds and was terminated. No current exchange data or snapshot was accepted. Network integration remains unverified in this environment.

## 2026-09-24 — Bybit AI Trading Skill candidate

- Source reviewed: https://github.com/bybit-exchange/skills (repository overview/README only). This is not a code/dependency audit and no commit has been approved for execution.
- Scope advertised includes account actions, trade execution, derivatives, transfers, and automatic updates, far beyond this project's research requirements. Instructions concerning interactive credentials are unsuitable for pasting secrets into this conversation.
- Decision: **not installed; not approved for execution**. Use the local public-data client instead. Before any future use, inspect and pin the exact skill version, modules and fetched executables, dependencies, authentication, permissions, data destinations, and update mechanism. Start with public data or read-only account access; project spot-only rules remain authoritative.

## 2026-09-24 — Research literature

- Source: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf ; author-hosted paper used for methodology in the prior review.
- Risks: external PDF/content and methodological claims that do not establish this project's trading edge.
- Decision: passive text reference only; no macros, attachments, downloaded executables, or financial claims adopted as strategy results. No further external research datasets or packages have been approved.

## Future review entry

Record date, exact URL/repository/version or hash where applicable, intended capability, data sent, permissions, executable/dependency/update inspection (if applicable), known limitations, mitigations, and approved/rejected scope. Record failures honestly; a failed fetch is not a completed audit.

## 2026-09-24 — Diagnostics and historical collection scope extension

- Same reviewed source, https://api.bybit.com, and public spot kline endpoint. No new provider, proxy, package, credential, or execution permission.
- Diagnostics perform DNS resolution, verified TLS handshake, and a one-candle public GET in separate local Python children, each limited to 12 seconds. Only proxy type names/config-presence flags are reported, never proxy URLs, credentials, resolver IPs, or account details. No DNS, proxy, firewall, certificate, or system settings are changed.
- The historical collector uses explicit start/end timestamps and reverse pagination with at most 100 pages per interval, 1,000 candles per page, a 15-second child deadline per request, and 0.25-second spacing. Files are limited to 90,000 execution bars per request window. There are no automatic retries, alternate hosts, or access-restriction workarounds. Abort on gaps, duplicates, wrong symbols, malformed data, or incomplete ranges; never synthesize missing exchange candles.
- Local datasets/configs are treated as data, loaded as bounded JSON (256 MB maximum for simulator inputs); no eval, dynamic imports, shell interpolation, or execution of downloaded content. Source/config/code hashes preserve reproducibility but do not authenticate a user-supplied dataset. Reports are separate from paper/live journals and never grant trading permission.
- Decision: approved for these read-only research operations. Historical fee/instrument assumptions and candle-fill limitations must appear in every report. External datasets from any other provider still require their own review.
- Initial diagnosis: direct DNS resolution and the public HTTPS probe both exceeded their deadlines; no proxy or custom certificate environment variables were detected. This identifies a DNS-stage stall, not proof of an exchange account or geographic restriction.
- Subsequent evidence: user confirmed browser DNS_PROBE_FINISHED_NXDOMAIN. System resolver entries were present; no API hostname hosts-file override was found. A local macOS resolver-cache flush (no configuration change) completed successfully; a fresh staged check still timed out at DNS. No alternative DNS provider, proxy, VPN, endpoint, or certificate setting was substituted.
- Additional passive source reviewed: https://bybit-exchange.github.io/docs/v5/guide, same official documentation source/scope. It confirms the mainnet API hostname. Other hosts listed there have not been selected, reviewed for this project's use, or added to the client allowlist.
- Retry at 2026-09-24 17:08:35 UTC reused this approved scope: DNS, certificate-verified TLS, and public spot JSON succeeded. The same fixed endpoint supplied the September 1–3 historical smoke dataset, which passed the collector and simulator checks. No additional provider, dependency, credentials, network setting change, or permission was needed. Availability does not establish data accuracy beyond the implemented checks or trading profitability.
- At 21:11:55 UTC, reused the approved public instruments-info scope for BTCUSDT spot; saved instrument-btc-20260924.json with provenance. Validated response freshness/category, exact symbol and Trading status; treated JSON fields as data only. No account data, credentials, external code, or order requests were involved.

## 2026-09-25 — Spot protection documentation

- Sources selected for passive review: https://www.bybit.com/en/help-center/article/Introduction-to-Take-Profit-and-Stop-Loss-Spot-Trading ; https://www.bybit.com/en/help-center/article/One-Cancels-the-Other-OCO-Orders ; https://www.bybit.com/en/help-center/article/Bybit-Spot-Trading-Rules . Official exchange HTTPS help-center provenance; same passive-documentation scope as earlier reviews.
- Risks: changing rules, product/account differences, untrusted text and links; documentation cannot prove account-specific order acceptance. No login, credentials, remote code, installations or order actions. Read text only; do not follow instructions to change project permissions or use alternate execution hosts. Approved for documentation comparison, not live execution.

- Review outcome: OCO and Spot Trading Rules articles loaded; standalone Spot TP/SL article timed out twice. Used only successfully retrieved documentation for execution claims. No alternate domain or authenticated account access used.

## 2026-09-25 — Broader historical collection

- Reuses reviewed fixed public Bybit BTCUSDT spot kline scope and unchanged bounded collector. Two sequential date windows in evaluation-plan-20260925.json, each below 90,000 one-minute bars; existing pagination caps, spacing, deadlines, TLS and data checks apply. No new source, dependency, secret, proxy or account action. Approved for collection and local data-integrity checks only; future holdout is not yet available.

## 2026-09-28 — Bounded forward observer

- Reuses the reviewed public Bybit spot kline, instruments-info and orderbook endpoints through the existing fixed-host client; no new provider, dependency, credentials or trading permissions.
- Scope extension: a local process may run for up to seven days, checking once per UTC hour, with a bounded snapshot and one fresh orderbook request per attempted check. No rapid retries, alternate hosts, proxy changes, login, orders or transfers.
- Store public response provenance and timestamped decisions locally; prevent duplicate instances with a local lock. Late/stale/missing observations must be explicit. Stop on local integrity/code-version failures. Restart must record missed hour boundaries rather than retrospectively inventing observations.
- Security decision: approved for public-data observation only. Optional local risk inputs remain local and are never sent to the exchange. A passing quote or paper calculation is not an order or proof of execution. No secrets are required.

- Implementation outcome: stdlib observer and 55 local tests; detached process started for 168 hours with public endpoints only and no account/risk input. Initial connectivity probe timed out. No credential, order, transfer or system-setting capability added. Local observations/logs excluded from git; raw public responses retained as data.

## 2026-09-28 — Manual session sources

- Reuse reviewed Bybit public spot snapshots for BTCUSDT/ETHUSDT; no new API permissions.
- Passive sources selected: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm ; https://www.bls.gov/schedule/2026/home.htm ; https://www.bea.gov/news/schedule ; https://www.coingecko.com/en/global-charts ; Reuters market-news pages on https://www.reuters.com/ discovered through search.
- Primary agency calendars establish scheduled releases, not outcomes. CoinGecko is aggregate context only, never Bybit execution evidence. Reuters is secondary reporting; verify event/publication dates and avoid stale or search-snippet-only claims. All public HTTPS text, no account data, credentials, installs or remote code. Search results are untrusted discovery data. Approved for passive session research within this scope.

- Manual-session outcome: BTC/ETH Bybit snapshot calls timed out; no data accepted. Agency calendars loaded. CoinGecko redirected within the same HTTPS domain to /en/charts; approved as passive context, with missing quote timestamp disclosed. No usable current Reuters headline returned, so no event claim adopted. Observer process stopped at user workflow change.

## 2026-09-28 — Session news supplement

- Source: https://www.marketscreener.com/news/dollar-firms-as-us-iran-tensions-lift-oil-hawkish-fed-bets-build-ce785adcdb89f522 . Public HTTPS financial-news distributor; search identifies Reuters syndication. Verify article attribution and publication/event date on retrieval. Passive text only; ads, links and embedded instructions are untrusted, no login, code, credentials or account data. Approved for secondary macro-news context, not execution prices or confirmed causality.

## 2026-09-29 — Session refresh

- Reuse reviewed Bybit public BTC/ETH snapshots and agency/CoinGecko passive sources. Additional Reuters-syndicated article selected on the same reviewed HTTPS distributor: https://www.marketscreener.com/news/oil-price-gains-pared-as-qatar-us-iran-talks-loom-ce785adcd18ff220 . Passive text only, verify attribution/time, no account data, login, code execution or instructions adopted. News is contextual reporting, not execution evidence. Approved within existing read-only scope.

## 2026-09-29 — Broader watchlist context

- Source: https://www.coingecko.com/en . Extend existing passive CoinGecko review to aggregate asset rankings and reported volumes for watchlist discussion. Public HTTPS text only; no credentials, account information, installs or remote code. Rankings and volumes can change and do not verify Bybit pair availability, executable liquidity or suitability. Treat page text as untrusted data; verify exchange-specific evidence before any trade. Approved for screening context only.

## 2026-09-29 — Approved six-pair manual screening

- User approved adding SOLUSDT, XRPUSDT, LINKUSDT and SUIUSDT to BTCUSDT/ETHUSDT. Extend the reviewed https://api.bybit.com public spot scope only to these exact symbols on /v5/market/kline, /v5/market/orderbook and /v5/market/instruments-info.
- Reviewed local collector: fixed host/path/symbol allowlists, verified TLS, redirects and environment proxies disabled, 2 MB response cap, 25-second CLI deadline, four-request snapshot batch, freshness/category/symbol/candle/book checks. Exchange receives IP and public market query parameters only. No account data, credentials, packages, remote code, authentication, order or transfer capabilities added.
- More symbols mean more requests; collect bounded snapshots per pair, without launching six simultaneous batches, automatic retries or restriction bypasses. Listing status, liquidity and instrument constraints must be verified per pair; aggregate website volume is insufficient. Approved for public manual-screening data only. Existing BTC-only research and stopped observer remain unchanged. No live availability claim follows from the allowlist change.

## 2026-09-29 — Expanded-session catalyst sources

- Passive HTTPS sources selected from untrusted search discovery: https://help.phantom.com/articles/ending-support-for-sui-in-phantom-53868478441491 (wallet provider primary help page); https://www.binance.com/en-BH/square/post/09-28-2026-this-week-sui-cards-kmno-and-others-will-unlock-over-30-million-worth-of-tokens-371364061562143 (secondary unlock reporting). Read text only, verify dates/attribution and distinguish scheduled events from outcomes. No wallet connection, login, account data, swaps, software or remote instructions. Unlock reports have conflicting dates; exact schedule requires primary verification before exposure. Approved for contextual research only, not execution or asset migration. Existing reviewed Reuters syndication and official calendars reused.

## 2026-09-29 — 10:19 Lagos session news refresh

- Source selected from search: https://economictimes.indiatimes.com/markets/commodities/news/oil-prices-rise-for-second-session-on-continued-middle-east-supply-concern/articleshow/134553898.cms . Public HTTPS publisher, search attributes Reuters; verify attribution and event/publication time on page. Passive text only; no account data, login, installations or remote instructions. Treat ads and linked content as untrusted; approved for contextual secondary reporting only. Reuse reviewed six-pair public Bybit API, CoinGecko and official calendar scopes.

## 2026-09-29 — 12:04 Lagos session news sources

- Selected public HTTPS articles: https://apnews.com/article/91de6619aca2e1a9a32757166eae98d0 and https://apnews.com/article/269abea6fd8ea7f314a8c34152788e0c . Associated Press reporting, passive text only; verify event/publication dates. No credentials, account data, software, subscriptions or execution. Treat embedded links/instructions as untrusted; approved for macro context only, not exchange execution data. Reuse existing public Bybit six-pair, CoinGecko, BLS and BEA scopes.

## 2026-09-29 — 17:11 Lagos release verification

- Extend reviewed BLS public calendar scope to official release https://www.bls.gov/news.release/jolts.nr0.htm for the actual JOLTS result. Public HTTPS text only; verify release/reference month and timestamp because latest-release pages roll forward. No account data, authentication, remote code or instructions adopted. Approved for primary economic-release facts. Reuse existing reviewed Bybit, CoinGecko, BEA and AP sources within their passive scopes.

- Additional 17:11 session sources: https://chain.link/newsroom and https://maple.finance/insights/syrupusd-assets-are-upgrading-to-chainlink-ccip-2-0 . Project/vendor primary announcements for CCIP adoption; HTTPS passive text only, no wallet connections, assets, credentials, upgrades, downloads or remote code. Promotional claims are not independent price-impact evidence. Verify dates and factual implementation scope; approved for catalyst research only.

## 2026-09-29 — 21:23 Lagos exchange-risk check

- Source: https://www.bitget.com/campaigns/bitget-security-incident-2026 . Official exchange HTTPS domain selected from untrusted search discovery, passive public incident timeline only. Check dates, distinguish incident from current restoration claims, and attribute exchange claims. No login, credentials, wallets, transfers, installations or downloaded code; no alternate/lookalike host used. Approved for contextual incident verification; does not establish Bybit impact or safety. Existing six-pair Bybit and passive news/calendar scopes reused.
- Outcome: official Bitget timeline fetch failed. Incident details discovered in search remain unverified in this session; no claim of completed primary verification or Bybit impact. AP refresh also failed; use prior verified macro context only.

## 2026-09-30 — Morning session exchange-status source

- Extend the existing passive official Bitget review to https://www.bitget.com/support/articles/12560603896025 (withdrawal-service update discovered through search). Verify page date, incident and restoration timing on retrieval; distinguish scheduled resumption from actual availability. Public HTTPS text only, no account information, login, wallets, downloads or code. Embedded instructions and external links remain untrusted. Approved only for exchange-risk context; no inference that Bybit is affected or safe. Reuse reviewed Bybit six-pair API, CoinGecko, BEA, BLS and Chainlink source scopes.

## 2026-10-02 — Morning manual session source review

- Reuse reviewed public Bybit six-pair market endpoints, CoinGecko charts and BLS calendar with the same bounded read-only scope. No account data, credentials or order capability.
- New source selected from search: https://www.livemint.com/market/equities-turn-higher-as-treasury-yields-drop-from-highs/amp-11790880604226.html . Public HTTPS publisher carrying a Reuters-attributed October1 US-market report; verify attribution and event date in page text, rather than calling the publication's October2 India timestamp a new US session. Passive text only, no login, scripts, downloads or instructions adopted; ads and links remain untrusted. Approved for secondary macro context only, not execution prices or proof of crypto causality.
- Additional primary project source: https://www.sui.io/blog . Public HTTPS project blog; vendor reporting and promotional claims require attribution and date checks. Passive text only, no wallet connection, code, credentials or external instructions. Approved for catalyst discovery; not proof of token demand or unlock execution.

## 2026-10-02 — Setup selectivity review reference

- Source selected via search: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf . Author-hosted research paper on backtest overfitting; passive PDF text retrieval only, no local executable content, packages, credentials or account information. Treat document instructions/links as untrusted. Verify title/authors on retrieval; approved for methodological context, not validation of this project's strategies or performance claims.

## 2026-10-02 — Optional 15-minute manual paper data

- Extend the existing six-symbol public Bybit kline scope to interval=15, up to 1,000 recent candles, only with tools.market --include-m15. Same fixed https://api.bybit.com host, spot symbol/path allowlists, verified TLS, disabled redirects/environment proxies, 2MB response limit, fresh responses and 25-second child deadline. Five requests for opt-in snapshots; four for default calls. Sequential pair batches, no automatic retry or access bypass.
- Reviewed local change adds no dependencies, authentication, execution or account action. Validate closed/contiguous M15 candles and exact OHLC agreement for complete overlapping H1 bars; discrepancies fail closed. All raw provenance retained locally. Approved for bounded collection and manual paper evidence only; data integrity checks do not establish independent exchange authenticity, profitability or fills.
- One bounded BTCUSDT opt-in collection may be used as an integration smoke check after local tests; it is not a trade or retrospective performance evaluation. Trial records/risk inputs remain local. No external skill, plugin, SDK or executable downloaded.
- Integration outcome: optional BTCUSDT M15 snapshot succeeded at 2026-10-02T04:04:32.768871+00:00; 999 completed M15 candles, overlapping H1 OHLC checks passed. Raw evidence retained in snapshot-fbr-smoke-20261002.json. No account/API-key access or order action. Synthetic tests verify safeguards; neither tests nor collection prove profitability or exchange fills.

## 2026-10-02 — Approved observation and accounting fixes

- Reuse only the previously reviewed fixed public Bybit spot host/endpoints/six symbols. New local tools/manual_observer.py uses Python standard library, verified collector requests, and an optional fresh post-confirmation book. No package, plugin, external code, credentials, account data, execution permission, notification destination or system setting is added. The exchange receives public query parameters and network metadata only.
- The recorder accepts a size-limited local JSON watch, validates allowed fields/levels, hashes accepted inputs/code, records gaps, refuses overwrite, locks its directory, and runs for at most six hours/25 checks. Each snapshot has a 25-second process deadline and a fresh book 15 seconds; it starts neither when insufficient run time remains. No retry on access denial/rate limits, endpoint fallback or automatic startup. Risks: inaccurate/changed exchange data, stale/partial evidence, local disk growth and sleep/network gaps. Mitigations: response/market/candle/chronology checks, finite runtime and data sizes, explicit missing states, no automatic trade or READY claim. Local hashes identify evidence, not authenticity or tamper-proof storage.
- Optional M15 now has an independent 15-second child deadline and structured sanitized failure metadata. Recoverable optional failure preserves validated core sources; HTTP 403/429 still propagates and stops collection. Required-source errors remain fatal. This limits a missing-data failure to the affected assessment without weakening mandatory price or risk checks.
- tools/manual_ledger.py is local-only standard-library JSONL replay with process locking and validation before append. It has no network/account capabilities. Operator-provided cards and proceeds remain untrusted evidence requiring review; arithmetic does not authenticate a signal or fill. Duplicate/backdated events, unsupported modes/resets, overlapping exposure and impossible ranges fail closed. Conservative ranges and latched halts avoid silently replacing a possible loss with a later winner. Retain backups; local files remain editable outside the tool.
- Decision: approved within this bounded public-read/local-evidence scope. One no-watch `--once` baseline smoke and offline reports may verify integration after synthetic tests. No multi-hour process, paper entry or actual order is started by the repair. Original registration remains unchanged; an amendment records new file hashes before scored observations.
- Integration outcome: the no-watch BTC baseline completed at 2026-10-02T04:40:19.432+00:00 with valid H1/H4/book/instrument data; its process stopped at 04:40:19.447 UTC after one check. Evidence directory: observations/manual-fbr-fix-smoke-20261002. Offline report shows one observed check, zero registered watches and zero paper positions. This verifies one public-data integration path, not a full watched trigger, M15 outage on the live service, or profitability.

## 2026-10-02 — Second approved review fixes

- Scope remains local Python standard-library changes to sizing, manual paper accounting and observation validation/reporting. No external skills, packages, downloads, new sources, permissions, credentials, accounts or endpoints are used. Tests use synthetic inputs and temporary directories only; no live feed is required to reproduce the six defects.
- Per-timeframe alignment retains source identity, 60-second freshness, closed-candle, continuity and cross-timeframe integrity checks. Separate detection/receipt timestamps and trailing-gap records prevent misleading opportunity/coverage counts. Existing finite runtime, no-order scope and access-denial/rate-limit stops remain required.
- The additional risk cap may only reduce allowed size. Quantity search applies exit maxima and conservative remaining daily/weekly allowances without raising percentage limits. Exposure reconciliation requires new evidence, a reason, and links to the outstanding entry/assessment; it retains superseded evidence and cannot clear latched halts or directly set account balances. Operator evidence still needs review; local records do not authenticate exchange fills.
- Decision: approved for local implementation and offline verification within existing scope. Preserve both earlier registration files and record fresh hashes in a second amendment before future scoring. No observer launch, paper trade, performance evaluation or account action is part of this repair.

## 2026-10-02 — Third approved review fixes

- Scope: local changes to tools/risk.py, tools/manual_observer.py and their synthetic tests. The exact arithmetic uses Python's bundled fractions module; no external skill, package, repository, download, website or API is introduced or used for this repair. No account information or credentials leave the workspace.
- Review covers rounding-aware quantity selection, known-deadline enforcement, unchanged risk caps and order minimums, missing-data diagnostics and termination. Risk: a naive descending quantity scan could consume excessive CPU for tiny increments; exact integer floor sums and binary search avoid scanning the order grid. Tests compare selected sizes with an independent exhaustive oracle and exercise sparse exact-threshold cases.
- Expiry must remain enforceable during a data outage, including requests completing after the deadline. Existing bounded public-data capabilities, access-denial/rate-limit halts and no-order scope remain intact. Tests substitute local clocks and data; no observer process or network request is started.
- Decision: approved for offline verification in the existing scope. Preserve previous manifests and record fresh hashes before future observations. Software tests and local hashes establish neither exchange-data authenticity nor profitable trading outcomes.

## 2026-10-02 — Fourth approved repair: data and evidence integrity

- Scope: local Python standard-library changes to the public-data collector, bounded manual observer, manual paper ledger and TPB paper journal, plus synthetic regression tests. No external skill, package, source, download, credential, endpoint or account capability is introduced. This repair uses no network requests or real trading/observation processes.
- Review targets: consistent completed H1/H4 candles before manual assessment, conservative expiry of the latest possible remaining setup sequence during outages, entry freshness after lock/replay delays, and one-position chronology through journal corrections. Partial history edges must not be mistaken for inconsistent complete candles; missing evidence must not become an invented signal or fill.
- Persistence risks: lock contention or suspension can stale a prechecked entry; a correction can temporarily remove evidence establishing flat exposure. Recheck time at publication, retain original observation times, preserve append-only history, and block unreliable performance reporting or new paper entries until corrections establish consistent chronology. Do not silently rewrite or repair existing ledger records.
- Decision: approved for offline implementation and tests within the user's requested fixes. Preserve all previous registrations and historical results; record updated code/test hashes in a new amendment before future scoring. Test success verifies software behavior, not exchange execution or profitability.
