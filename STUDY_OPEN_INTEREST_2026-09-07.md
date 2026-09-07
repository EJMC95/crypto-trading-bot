# OPEN INTEREST — REFUSED ON THE DATA

**The supplied series is not open interest.**

```
{
 "n": 65956,
 "up": 63753,
 "down": 0,
 "flat": 2203,
 "non_falling_frac": 1.0,
 "why": "the series never falls (65956 of 65956 steps non-falling) \u2014 this is a CUMULATIVE COUNTER, not an open-interest LEVEL, so divergence is untestable on it"
}
```

the series never falls (65956 of 65956 steps non-falling) — this is a CUMULATIVE COUNTER, not an open-interest LEVEL, so divergence is untestable on it

Real point-in-time OI is `orderBookDetails.open_interest`; its HISTORY exists only inside `market_context`'s own state (`oi_ntl`, hourly), which is DB-side and not on `/bus.json`. So the price/OI hypothesis **cannot be tested from outside the containers** until that history is exposed — and that, not a verdict, is the honest deliverable.

The machinery is sound: the selftest's planted-signal positive control passes, so a silent 'no signal' here would have been the data, not the method.
