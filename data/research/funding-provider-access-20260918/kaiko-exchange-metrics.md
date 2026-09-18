> For the complete documentation index, see [llms.txt](https://docs.kaiko.com/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://docs.kaiko.com/rest-api/analytics/derivatives-risk-indicators/exchange-provided-metrics.md).

# Exchange-provided metrics

Derivatives Risk endpoint

{% hint style="info" %}

### This data is included in the following Kaiko packages:

* Kaiko Derivatives Risk Indicators \[Basic Tier]
* Kaiko Derivatives Risk Indicators \[Advanced Tier]
  {% endhint %}

### What is this endpoint for? <a href="#what-is-this-endpoint-for" id="what-is-this-endpoint-for"></a>

This endpoint returns exchange-provided metrics such as open interest, funding rates, and option greeks.

### Endpoint

```http
https://{eu/us}.market-api.kaiko.io/v2/data/derivatives.v2/risk
```

### Path Parameters

| Parameter | Required? | Example                       |
| --------- | --------- | ----------------------------- |
| `region`  | Yes       | Choose between `eu` and `us`. |

### Query Parameters

<table><thead><tr><th width="173">Parameter</th><th width="98">Required</th><th width="374">Description</th><th>Example</th></tr></thead><tbody><tr><td><code>exchange</code></td><td>Yes</td><td>Should be one of the exchanges currently supported</td><td><code>okex</code></td></tr><tr><td><code>instrument_class</code></td><td>Yes</td><td><code>future</code>, <code>perpetual-future</code>, or <code>option</code></td><td><code>future</code></td></tr><tr><td><code>instrument</code></td><td>Yes</td><td>Instrument <code>code</code>. <br><br>See <a data-mention href="broken://pages/8ywkQXfxfv1FjtyspEaU">Broken link</a><br><br>One instrument returned per query.</td><td><code>btcusdt250117</code></td></tr><tr><td><code>interval</code></td><td>No</td><td>Interval period (can be one of <code>1m</code>, <code>1h</code>, <code>4h</code>, and <code>1d</code>). Default <code>1m</code><br><br>When you query data using an<code>interval</code> greater than one minute, we'll return the data from the last minute of that time period. For example, if you query data for <code>09:00</code> with the <code>interval</code> set at <code>1h</code>, we'll return data from <code>09:59</code> (since that's the last minute of the 09:00-10:00 hour period). </td><td><code>1h</code></td></tr><tr><td><code>page_size</code></td><td>No</td><td>Number of snapshots to return data for. (default: 100, min: 1, max: 1000). <br><br>See <a data-mention href="/rest-api/general/getting-started/pagination.md">Pagination</a></td><td><code>10</code></td></tr><tr><td><code>sort</code></td><td>No</td><td>Return the data in ascending (asc) or descending (desc) order. Default desc</td><td><code>asc</code></td></tr><tr><td><code>start_time</code></td><td>No</td><td>Starting time in ISO 8601 (inclusive).</td><td><code>2025-01-01T00:00:00.000Z</code></td></tr><tr><td><code>end_time</code></td><td>No</td><td>Ending time in ISO 8601 (exclusive).</td><td><code>2025-01-04T00:00:00.000Z</code></td></tr></tbody></table>

### Fields: Perpetual-Future

<table><thead><tr><th width="214">Field</th><th width="341">Description</th><th>Example</th></tr></thead><tbody><tr><td><code>timestamp</code></td><td>Timestamp at which the interval begins. In milliseconds.</td><td><code>1650441900000</code></td></tr><tr><td><code>24h_volume</code></td><td>The volume of the trades executed in the last 24 hours (can be in base_asset, quote_asset or the number of contracts)</td><td><code>5270648</code></td></tr><tr><td><code>open_interest</code></td><td>The total outstanding number of contracts (units in which open interest metrics are quoted vary by exchange)</td><td><code>1127623</code></td></tr><tr><td><code>funding_rate</code></td><td>The current funding rate.</td><td><code>-0.0000756735759807</code></td></tr><tr><td><code>predicted_funding_rate</code></td><td>The predicted funding rate for the next period.</td><td><code>-0.0000845044644161</code></td></tr></tbody></table>

### Fields: Future

<table><thead><tr><th width="214">Field</th><th width="341">Description</th><th>Example</th></tr></thead><tbody><tr><td><code>timestamp</code></td><td>Timestamp at which the interval begins. In milliseconds.</td><td><code>1650441900000</code></td></tr><tr><td><code>24h_volume</code></td><td>The volume of the trades executed in the last 24 hours (can be in base_asset, quote_asset or the number of contracts)</td><td><code>5270648</code></td></tr><tr><td><code>open_interest</code></td><td>The total outstanding number of contracts (units in which open interest metrics are quoted vary by exchange)</td><td><code>1127623</code></td></tr><tr><td><code>time_to_expiry</code></td><td>The number of minutes remaining before expiry.</td><td><code>41504</code></td></tr><tr><td><code>nearby</code></td><td>The soonest expiring contract with the same base &#x26; quote asset on the specified exchange</td><td>boolean value</td></tr><tr><td><code>quarterly_nearby</code></td><td>The soonest expiring <strong>quarterly</strong> contract with the same base &#x26; quote asset on the specified exchange</td><td>boolean value</td></tr><tr><td><code>settlement_price</code></td><td>Settlement price calculated at the end of the trading day for the contract.</td><td><code>106610</code></td></tr><tr><td><code>settlement_timestamp</code></td><td>Time of calculated settlement price.</td><td><code>0.0065</code></td></tr></tbody></table>

### Fields: Option

<table><thead><tr><th width="214">Field</th><th width="341">Description</th><th>Example</th></tr></thead><tbody><tr><td><code>timestamp</code></td><td>Timestamp at which the interval begins. In milliseconds.</td><td><code>1650441900000</code></td></tr><tr><td><code>24h_volume</code></td><td>The volume of the trades executed in the last 24 hours (can be in base_asset, quote_asset or the number of contracts)</td><td><code>5270648</code></td></tr><tr><td><code>open_interest</code></td><td>The total outstanding number of contracts (units in which open interest metrics are quoted vary by exchange)</td><td><code>1127623</code></td></tr><tr><td><code>time_to_expiry</code></td><td>The number of minutes remaining before expiry.</td><td><code>41504</code></td></tr><tr><td><code>nearby</code></td><td>The soonest expiring contract with the same base &#x26; quote asset on the specified exchange</td><td>boolean value</td></tr><tr><td><code>quarterly_nearby</code></td><td>The soonest expiring <strong>quarterly</strong> contract with the same base &#x26; quote asset on the specified exchange</td><td>boolean value</td></tr><tr><td><code>ask_iv</code></td><td>Implied volatility for the best ask.</td><td><code>57.5</code></td></tr><tr><td><code>bid_iv</code></td><td>Implied volatility for the best bid.</td><td><code>65.4</code></td></tr><tr><td><code>mark_iv</code></td><td>The implied volatility for the mark price.</td><td><code>69.42</code></td></tr><tr><td><code>delta</code></td><td>The delta value for the option.</td><td><code>0.8841</code></td></tr><tr><td><code>gamma</code></td><td>The gamma value for the option.</td><td><code>0.00003</code></td></tr><tr><td><code>rho</code></td><td>The rho value for the option.</td><td><code>21.26122</code></td></tr><tr><td><code>theta</code></td><td>The theta value for the option.</td><td><code>-26.18193</code></td></tr><tr><td><code>vega</code></td><td>The vega value for the option.</td><td><code>2.36321</code></td></tr><tr><td><code>settlement_price</code></td><td>Settlement price calculated at the end of the trading day for the contract.</td><td><code>106610</code></td></tr><tr><td><code>settlement_timestamp</code></td><td>Time of calculated settlement price.</td><td><code>0.0065</code></td></tr></tbody></table>

### Request examples

{% tabs %}
{% tab title="cURL" %}
{% code overflow="wrap" %}

```url
curl --compressed -H 'Accept: application/json' -H 'X-Api-Key: <client-api-key>' \
  'https://us.market-api.kaiko.io/v2/data/derivatives.v2/risk?exchange=okex&instrument_class=perpetual-future&instrument=btc-usdt&page_size=2'
```

{% endcode %}
{% endtab %}

{% tab title="Python" %}
{% code overflow="wrap" %}

```python
##### 1. Import dependencies #####
import requests
import pandas as pd

##### 2. Choose the value of the query's parameters #####
# ---- Required parameters ---- #
exchange = "okex"
instrument_class = "perpetual-future"
instrument = "btc-usdt"

# ---- Optional parameters ---- #
interval = "1h"
sort = "desc"
page_size = 100
start_time= None
end_time= None

# ---- API key configuration ---- #
api_key = "YOUR_API_KEY"

##### 3. Get the data #####
# ---- Function to run an API call ---- # 
# Get the data in a dataframe --------- # 

def get_kaiko_data(api_key: str, exchange: str, instrument_class: str, instrument: str, start_time: str, end_time: str, interval: str, sort: str, page_size: int):
    headers = {'Accept': 'application/json', 'X-Api-Key': api_key}
    
    url = f'https://us.market-api.kaiko.io/v2/data/derivatives.v2/risk'
    params = {
        "start_time": start_time,
        "end_time": end_time,
        "sort": sort,
        "page_size": page_size,
        "interval": interval,
        "exchange": exchange,
        "instrument_class": instrument_class,
        "instrument": instrument
    }

    try:
        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status() 
        data = res.json()
        if 'data' not in data:
            print("No data returned.")
            return pd.DataFrame() 
        df = pd.DataFrame(data['data'])

        # Handle pagination with continuation token
        while 'next_url' in data:
            next_url = data['next_url']
            if next_url is None:
                break
            res = requests.get(next_url, headers=headers)
            res.raise_for_status()
            data = res.json()
            if 'data' in data:
                df = pd.concat([df, pd.DataFrame(data['data'])], ignore_index=True)
        return df

    except requests.exceptions.RequestException as e:
        print(f"API request error: {e}")
        return pd.DataFrame() 

# ---- Get the data ---- #
df = get_kaiko_data(api_key=api_key, exchange=exchange, instrument_class=instrument_class, instrument=instrument, interval=interval, start_time=start_time, end_time=end_time, sort=sort, page_size=page_size)
print (df)
```

{% endcode %}
{% endtab %}

{% tab title="BigQuery" %}
Information from this endpoint can be accessed through Google BigQuery. \
\
To get started, read our [guide](broken://spaces/zwO3AMVXsp37KK2FngVc/pages/LFIZ1UwRtOxTg308jneZ).
{% endtab %}
{% endtabs %}

### Response example

```json
{
    "query": {
        "page_size": "2",
        "exchange": "okex",
        "instrument_class": "perpetual-future",
        "instrument": "btc-usdt",
        "sort": "desc",
        "data_version": "v2",
        "commodity": "derivatives",
        "request_time": "2022-04-28T10:17:48.180Z"
    },
    "time": "2022-04-28T10:17:48.698Z",
    "timestamp": 1651141068698,
    "data": [
        {
            "timestamp": 1651141020000,
            "24h_volume": "10428503",
            "open_interest": "1084816",
            "funding_rate": "-0.0001225804461251",
            "predicted_funding_rate": "-0.0000652655998942"
        },
        {
            "timestamp": 1651140960000,
            "24h_volume": "10423219",
            "open_interest": "1086823",
            "funding_rate": "-0.0001225804461251",
            "predicted_funding_rate": "-0.0000654154039082"
        },

    ],

    /* ... */

    "access": {
        "access_range": {
            "start_timestamp": 1646006400,
            "end_timestamp": null
        },
        "data_range": {
            "start_timestamp": null,
            "end_timestamp": null
        }
    }
}
```


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation dynamically by asking a question.

Perform an HTTP GET request on the current page URL with the `ask` query parameter, and the optional `goal` query parameter:

```
GET https://docs.kaiko.com/rest-api/analytics/derivatives-risk-indicators/exchange-provided-metrics.md?ask=<question>&goal=<endgoal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is optional and describes the broader end goal you are ultimately trying to accomplish on behalf of the user. GitBook uses it to tailor the answer towards what is most useful for that goal.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
