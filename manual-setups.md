# Manual spot setups — version 1

Approved workflow: discretionary analysis, user execution, separate records from TPB-v1. These definitions make judgments reviewable; they have no established win rate or profitable expectancy. Date: 2026-09-28. Spot longs only; 4-hour context and 1-hour triggers. No obligation to trade each day.

Use closed candles only. For repeatable chart annotation, a confirmed swing high exceeds the highs of the two candles before and the two after it; a confirmed swing low is below the lows of those four candles. It is usable only after the second following candle closes. Equal extremes do not qualify under this convention. Record swing timestamps and prices, not hindsight labels. These are initial operational conventions, not optimized parameters.

## MPB-v1: trend pullback

1. Context: the last two confirmed 4-hour swing highs and last two confirmed swing lows are successively higher. Latest closed 4-hour candle remains above the most recent confirmed swing low. If the structure cannot be established, this setup does not qualify.
2. Location: before the trigger, mark a numeric support zone based on a previously broken confirmed 4-hour swing high. Record its boundaries, originating candles and most recent relevant resistance. A pullback must touch that zone; do not redraw it after seeing the outcome.
3. Trigger: after that touch, a completed 1-hour candle closes above the zone's upper boundary and above the previous hourly candle's high. Record the trigger candle and an explicit entry range/maximum derived from the stop, resistance and net reward/risk. No entry solely because a candle is green.
4. Invalidation: a completed hourly close below the zone's lower boundary before entry cancels the plan. Protective stop is below the lowest hourly low from first zone touch through trigger, by at least one price tick; specify any wider structural buffer before entry. Skip if the resulting risk/size or net reward/risk is unacceptable.
5. Target: a numeric target before the nearest identified overhead resistance, with its origin recorded. If that does not support at least 2:1 net reward/risk, reject the trade rather than push the target beyond resistance.

## MBR-v1: breakout retest

1. Context: same confirmed rising 4-hour swing structure as MPB-v1. This initial definition excludes countertrend breakouts.
2. Location: mark a numeric resistance zone around a confirmed 4-hour swing high before breakout; record boundary selection and candle timestamps. Identify the next overhead resistance separately.
3. Trigger: a completed 1-hour candle closes above the zone's upper boundary. A later hourly candle retests the marked zone and closes above its upper boundary. The retest must occur after the breakout candle; do not infer the sequence from one candle's high and low.
4. Invalidation: an hourly close below the lower boundary after breakout and before entry cancels the plan. Initial protective stop is below the retest candle's low by at least one tick; specify any wider structural buffer before entry. Record the trigger and numeric entry range; reject a price beyond the maximum.
5. Target: before the next identified overhead resistance. Reject if there is no defensible target providing at least 2:1 net reward/risk after costs.

## Shared execution rules

- Before a setup becomes READY, fill every required trade-card field and confirm the account limits. Evidence may come from timestamped Bybit charts and quotes supplied by the user when the API is unavailable; clearly identify the source and any missing depth.
- The card must specify exact plan expiry, maximum holding time and time-exit action before entry. Default entry opportunity expires at the next 1-hour candle close following the trigger, or sooner on invalidation, changed conditions or the stated deadline. Quote freshness still expires after 60 seconds: a one-hour opportunity is not permission to use an hour-old quote.
- Record imminent macro events and an explicit event-exposure decision before entry. If the event's possible volatility cannot be accommodated by the execution/risk plan, wait. News alone never authorizes entry or relaxes the structural conditions.
- Single position; single fixed target by default. No adding to losses, widening stops or automatic breakeven/trailing changes. Any alternative management/partial-exit rule must be written before entry, sized correctly and evaluated separately.
- Plan the stop mechanism, net sellable inventory and what the user will do if protection fails. If no workable protection/exit contingency can be established, keep the plan CONDITIONAL or WAIT. Do not count an unsubmitted or unconfirmed order as active protection.
- Changing swing conventions, trigger rules or management after observing results requires a new version and a recorded rationale. Preserve original cards and results. These setups are separate from TPB-v1 and its frozen research periods.
