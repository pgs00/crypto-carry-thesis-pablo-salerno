> For the complete documentation index, see [llms.txt](https://gitbook-docs.coinmetrics.io/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://gitbook-docs.coinmetrics.io/market-data/market-data-overview/market-funding-rates.md).

# Market Funding Rates

## Overview

Funding rates are periodic payments exchanged between the long and short holders of a perpetual futures contract to keep its price aligned with the underlying spot or index price. Unlike traditional futures, perpetual contracts never expire, so there is no settlement date that forces convergence. The funding mechanism substitutes for that: it answers what it costs to hold a leveraged perpetual position, and which side of the market is paying to stay in it. Traders, risk teams, and researchers use funding rates to measure the cost of carry, gauge crowding and sentiment, and compare the economics of perpetuals across venues.

Coin Metrics collects funding rates from perpetual futures markets across its exchange coverage universe and serves them as a per-market time series over the HTTP endpoint [`/timeseries/market-funding-rates`](https://docs.coinmetrics.io/api/v4/#operation/getTimeseriesMarketFundingRates).

{% hint style="info" %}
**Realized, not predicted.** This page covers the **realized** funding rate: the rate actually calculated over the previous funding interval and used to determine the funding payment. Some exchanges also publish a forward estimate of the next rate, which they may call the predicted, real-time, or next funding rate. For that series, see [Market Funding Rates Predicted](/market-data/market-data-overview/market-funding-rates-predicted.md).
{% endhint %}

## At a Glance

<table data-full-width="true"><thead><tr><th>Data type</th><th>Entities</th><th width="159">Frequency / cadence</th><th>Unit</th><th>Primary endpoint</th><th>Coverage</th></tr></thead><tbody><tr><td>Realized perpetual-futures funding rates</td><td>Markets (perpetual futures)</td><td>Event-driven. One observation per market at the end of each funding interval (commonly every 8 hours, but venue-specific, for example hourly on some venues)</td><td>Funding rate as a decimal fraction over the period (for example <code>0.0010</code> = 0.10%). The <code>period</code> and <code>interval</code> are returned as separate duration fields</td><td><code>/timeseries/market-funding-rates</code></td><td><a href="https://coverage.coinmetrics.io/market-funding-rates-v2">🔗</a></td></tr></tbody></table>

## Schema

One observation is the realized funding rate for one market at the end of one funding interval. Every observation carries the fields below. The columns are the response schema for `/timeseries/market-funding-rates`.

| Field           | Type               | Description                                                                                                                                                                                                                                                                                                                                                        | Notes       |
| --------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| `market`        | string             | Unique name of the market. Perpetual futures markets follow the `exchange-symbol-future` convention (for example `binance-BTCUSDT-future`).                                                                                                                                                                                                                        | Required    |
| `time`          | string (date-time) | The event time for the observation, in ISO 8601 with nanosecond precision. It marks the end of the funding interval the rate applies to. For most venues this is the exchange-reported time. For venues that report only a snapshot, it is the aligned interval-end time. See [Timestamps and timeseries normalization](#timestamps-and-timeseries-normalization). | Required    |
| `rate`          | string (decimal)   | The realized funding rate for the interval, expressed as a decimal fraction over the `period`. For example a `rate` of `0.0010` represents 0.10% applied each period. A positive rate means longs pay shorts, a negative rate means shorts pay longs. See [Sign convention and units](#sign-convention-and-units).                                                 | All markets |
| `period`        | string             | The length of time the rate applies to, that is, how often funding is calculated and exchanged between long and short holders. Returned as an `HH:MM:SS` duration (for example `08:00:00`). See [Period, interval, and annualization](#period-interval-and-annualization).                                                                                         | All markets |
| `interval`      | string             | The length of time over which the input data for the rate is measured. Returned as an `HH:MM:SS` duration. For venues that calculate funding continuously, this is set to `00:00:00.001` by convention. See [Period, interval, and annualization](#period-interval-and-annualization).                                                                             | All markets |
| `database_time` | string (date-time) | The time Coin Metrics stored the observation, in ISO 8601 with nanosecond precision. Use this for the exact instant a value was recorded.                                                                                                                                                                                                                          | Required    |

{% hint style="info" %}
**Conventions.** The `rate` is returned as a JSON **string** to preserve precision. Timestamps are UTC ISO-8601 with nanosecond resolution: `time` is the exchange-reported event time (the end of the funding interval), and `database_time` is when Coin Metrics stored the observation. The `period` and `interval` fields are `HH:MM:SS` durations. The `rate` is a decimal fraction over the `period`, not a percentage or an annualized number (see [Period, interval, and annualization](#period-interval-and-annualization)).
{% endhint %}

## Methodology

Funding rates are reported by each exchange under its own mechanism design, and Coin Metrics records them as a harmonized per-market time series rather than re-deriving the payments. The mechanics below cover how the data is collected, how the rate is signed and denominated, how the `period` and `interval` differ, how observations are timestamped, and how duplicates are removed.

### Collection

Coin Metrics collects realized funding rates from the perpetual futures markets of the exchanges in its coverage universe, using whichever method a venue supports:

* **Streaming.** Where an exchange pushes funding over a websocket, Coin Metrics records each update as the exchange sends it.
* **Polling.** Where funding is available only over a REST endpoint, Coin Metrics polls it and records the current value for each market.
* **Historical backfill.** History is loaded from each exchange's historical funding endpoint so that the series extends back to the start of coverage.

For the authoritative, current list of markets, exchanges, and history start dates, see the [coverage page](https://coverage.coinmetrics.io/market-funding-rates-v2).

### Sign convention and units

The `rate` is a decimal fraction that represents the return over one `period`, so a `rate` of `0.0010` is 0.10% over that period. The sign follows the direction of the payment:

* When the perpetual price trades above the underlying spot or index price, the rate is **positive** and long holders pay short holders.
* When the perpetual price trades below it, the rate is **negative** and short holders pay long holders.

This creates an incentive to take the position that pushes the perpetual price back toward spot. Funding payments are applied to the notional value of the position and do not change the position's size, so funding rates are not compounded across periods.

### Period, interval, and annualization

Two duration fields describe the timing of the rate, and they are not the same thing:

* `period` is how long the rate applies to, that is, how often funding is calculated and exchanged. Many venues use an 8 hour period, some use 1 hour.
* `interval` is the window of input data used to compute the rate. It is often equal to the `period`, but not always. Some venues measure inputs over a longer window than the payment period, and some calculate funding continuously, in which case the `interval` is set to `00:00:00.001` by convention.

Because venues use different periods, funding rates are not directly comparable until they are put on a common basis. To annualize a rate for cross-venue comparison, scale it by the number of periods in a year. Since funding is not compounded, this is a simple multiplication:

$$
r\_{\text{annual}} = r \times \frac{1\ \text{year}}{\text{period}}
$$

For example, an 8 hour `rate` of `0.0001` annualizes to roughly `0.0001 * (8760h / 8h)`, or about 10.95% per year.

### Timestamps and timeseries normalization

Exchanges differ in how they report the timestamp for a funding rate. Many publish funding as a time series of equally spaced points whose timestamps mark when the rate and payments are calculated. Others publish only a snapshot of the current rate at query time, which requires transformation to build a series. Regardless of how a venue reports it, Coin Metrics stores funding as a time series with one observation at the end of each funding interval, and returns that exchange-reported event time in the `time` field. The separate `database_time` records when the observation was stored, so the gap between the two measures collection lag.

### Deduplication

Coin Metrics runs redundant collectors for resilience, so the same observation can be produced more than once. Observations are keyed by market and event time, so two observations for the same market at the same `time` collapse to a single stored point. This holds across the streaming, polling, and historical backfill paths, which lets them overlap without creating duplicate rows.

## Accessing the Data

Funding rates are available over HTTP for historical queries and for the latest observations. There is no websocket stream for this data type.

Query one or more markets over a time range at `/timeseries/market-funding-rates`, or use `limit_per_market` for the most recent observations. The `markets` parameter accepts a comma-separated list or wildcard patterns such as `binance-*`, `*USDT-future`, or `*-future`, so you can query many markets in one call.

{% tabs %}
{% tab title="Python Client" %}

```python
import os
from datetime import timedelta
from coinmetrics.api_client import CoinMetricsClient

client = CoinMetricsClient(os.environ["CM_API_KEY"])

# Funding rates over a time range, fetched in parallel as a DataFrame.
df = client.get_market_funding_rates(
    markets=["binance-BTCUSDT-future"],
    start_time="2025-01-01",
    end_time="2025-02-01",
    format="json_stream",
).parallel(time_increment=timedelta(days=7)).to_dataframe()

print(df)

# For just the latest observations, use limit_per_market instead (uses format="json"):
# client.get_market_funding_rates(markets=["binance-BTCUSDT-future"], limit_per_market=5).to_dataframe()
```

{% endtab %}

{% tab title="Shell" %}

```shell
curl --compressed "https://api.coinmetrics.io/v4/timeseries/market-funding-rates?markets=binance-BTCUSDT-future&limit_per_market=5&page_size=10000&api_key=$CM_API_KEY"
```

{% endtab %}

{% tab title="Python" %}

```python
import os
import requests

response = requests.get(
    "https://api.coinmetrics.io/v4/timeseries/market-funding-rates",
    params={
        "markets": "binance-BTCUSDT-future",
        "limit_per_market": 5,
        "page_size": 10000,
        "api_key": os.environ["CM_API_KEY"],
    },
).json()
```

{% endtab %}
{% endtabs %}

Full parameter reference: see the API Reference for [`/timeseries/market-funding-rates`](https://docs.coinmetrics.io/api/v4/#operation/getTimeseriesMarketFundingRates).

## Examples

The examples below show the latest observations for two markets with different funding conventions. The `rate` is returned as a JSON string.

### Example: 8-hour funding

The latest funding rates for `binance-BTCUSDT-future`, where the rate applies every 8 hours and is calculated over an 8 hour interval. [Run this query](https://api.coinmetrics.io/v4/timeseries/market-funding-rates?markets=binance-BTCUSDT-future\&limit_per_market=3\&api_key=YOUR_API_KEY).

```json
{
  "data": [
    {
      "market": "binance-BTCUSDT-future",
      "time": "2026-07-22T08:00:00.000000000Z",
      "database_time": "2026-07-22T08:02:52.071885000Z",
      "rate": "0.00005448",
      "period": "08:00:00",
      "interval": "08:00:00"
    },
    {
      "market": "binance-BTCUSDT-future",
      "time": "2026-07-22T16:00:00.000000000Z",
      "database_time": "2026-07-22T16:03:01.375762000Z",
      "rate": "0.00001443",
      "period": "08:00:00",
      "interval": "08:00:00"
    },
    {
      "market": "binance-BTCUSDT-future",
      "time": "2026-07-23T00:00:00.000000000Z",
      "database_time": "2026-07-23T00:00:18.932661000Z",
      "rate": "-0.00000343",
      "period": "08:00:00",
      "interval": "08:00:00"
    }
  ]
}
```

### Example: hourly funding measured over a longer window

The latest funding rates for `kraken-PF_XBTUSD-future`, where the rate applies every hour (`period` `01:00:00`) but is measured over a 4 hour window (`interval` `04:00:00`). This shows why `period` and `interval` are separate fields. [Run this query](https://api.coinmetrics.io/v4/timeseries/market-funding-rates?markets=kraken-PF_XBTUSD-future\&limit_per_market=3\&api_key=YOUR_API_KEY).

```json
{
  "data": [
    {
      "market": "kraken-PF_XBTUSD-future",
      "time": "2026-07-24T15:00:00.000000000Z",
      "database_time": "2026-07-24T15:01:03.694227000Z",
      "rate": "0.000014926058333333",
      "period": "01:00:00",
      "interval": "04:00:00"
    },
    {
      "market": "kraken-PF_XBTUSD-future",
      "time": "2026-07-24T16:00:00.000000000Z",
      "database_time": "2026-07-24T16:02:44.712852000Z",
      "rate": "0.000019772683333333",
      "period": "01:00:00",
      "interval": "04:00:00"
    },
    {
      "market": "kraken-PF_XBTUSD-future",
      "time": "2026-07-24T17:00:00.000000000Z",
      "database_time": "2026-07-24T17:19:30.123135000Z",
      "rate": "0.000008173816666667",
      "period": "01:00:00",
      "interval": "04:00:00"
    }
  ]
}
```

## Coverage

{% embed url="<https://coverage.coinmetrics.io/market-funding-rates-v2>" %}

## Usage

* **Current cost of carry.** Use `limit_per_market` for a quick "latest N" look at a market's funding, or a wildcard such as `*-future` to scan many markets at once.
* **History and backfill.** Use a `start_time` / `end_time` range with `.parallel(time_increment=…)` to pull long histories efficiently.
* **Cross-venue comparison.** Convert rates to a common basis before comparing, using the `period` field to annualize (see [Period, interval, and annualization](#period-interval-and-annualization)).
* **Positioning and sentiment.** Read the sign and magnitude of the rate to see which side is paying and how strong the imbalance is.
* **Derivatives context.** Combine funding with [Market Open Interest](/market-data/market-data-overview/market-open-interest.md) and [Market Liquidations](/market-data/market-data-overview/market-liquidations.md) on the same markets to study leverage build-up and unwind, and with the [Funding Rate Metrics](/market-data/market-data-overview/funding-rate-metrics.md) for a coverage-wide view.

## Limitations

* **Conventions vary by exchange.** Each venue sets its own funding mechanism, `period`, and `interval`, so raw rates are not comparable across venues until they are put on a common basis. Annualize using the `period` before comparing (see [Period, interval, and annualization](#period-interval-and-annualization)).
* **Realized rate only.** This series is the rate calculated over the previous interval. For the forward estimate of the next rate, use [Market Funding Rates Predicted](/market-data/market-data-overview/market-funding-rates-predicted.md).
* **Zero and near-zero rates are valid.** Some venues can report a funding rate of `0`. For example, Bitfinex does not require a funding payment when the average spread over the funding period stays within a small band, so long stretches of `0` are expected rather than missing data.
* **Snapshot venues are transformed into a series.** For exchanges that publish only a current-rate snapshot rather than a time series, Coin Metrics reconstructs the series with one observation per funding interval (see [Timestamps and timeseries normalization](#timestamps-and-timeseries-normalization)).

## FAQ

### What is the difference between the `period` and `interval` fields?

They describe two different things. The `interval` is the window of input data used to calculate the rate. Many exchanges use a 1 hour or 8 hour input window, and for exchanges that calculate funding continuously the `interval` is set to `00:00:00.001` by convention. The `period` is how long the resulting rate applies to, that is, how often funding payments are calculated and exchanged between long and short holders. The two are often equal (for example 8 hours and 8 hours), but not always: a venue can report an hourly rate measured over a 4 hour window, in which case `period` is `01:00:00` and `interval` is `04:00:00`.

### How can I annualize the funding rate to compare across exchanges?

Because exchanges use different periods, scale each rate to a common basis using the `period` field. Since funding payments are applied to the position value and are not compounded, annualizing is a simple multiplication by the number of periods in a year:

$$
r\_{\text{annual}} = r \times \frac{1\ \text{year}}{\text{period}}
$$

For example, an 8-hour rate of `0.00005` (near the Binance level in the [example above](#example-8-hour-funding)) annualizes to `0.00005 × (8760h / 8h)`, or about 5.5% per year.

### What determines the frequency of funding rates data?

A market produces a new observation at the end of each funding interval, so the frequency follows the venue's funding schedule (commonly every 8 hours, hourly on some venues). See the [coverage page](https://coverage.coinmetrics.io/market-funding-rates-v2) for the markets available per exchange.

### Why are there so many funding rate values of `0` for Bitfinex?

Bitfinex allows a `0` funding rate. Under [Bitfinex's funding rate methodology](https://www.bitfinex.com/legal/derivative/funding), a funding payment is only required when the average spread over the funding period is greater than 0.05% or less than -0.05%. When the average spread stays within that band, no payment is required and the rate is `0`.

## Related

* [Market Funding Rates Predicted](/market-data/market-data-overview/market-funding-rates-predicted.md): the forward estimate of the next funding rate for a market.
* [Funding Rate Metrics](/market-data/market-data-overview/funding-rate-metrics.md): the open-interest-weighted aggregate and cumulative funding rate across markets, by asset and exchange-asset.
* [Market Open Interest](/market-data/market-data-overview/market-open-interest.md): outstanding contracts on the same derivatives markets.
* [Market Liquidations](/market-data/market-data-overview/market-liquidations.md): forced closes on the same derivatives markets.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation dynamically by asking a question.

Perform an HTTP GET request on the current page URL with the `ask` query parameter, and the optional `goal` query parameter:

```
GET https://gitbook-docs.coinmetrics.io/market-data/market-data-overview/market-funding-rates.md?ask=<question>&goal=<endgoal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is optional and describes the broader end goal you are ultimately trying to accomplish on behalf of the user. GitBook uses it to tailor the answer towards what is most useful for that goal.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
