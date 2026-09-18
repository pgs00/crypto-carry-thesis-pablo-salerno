> For the complete documentation index, see [llms.txt](https://docs.tardis.dev/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://docs.tardis.dev/api/instruments-metadata-api.md).

# Instruments Metadata API

Tick sizes, contract multipliers, base/quote currencies and expiration dates

Use the Instruments Metadata API to discover exchange-native symbol IDs and instrument details for replay, streaming, and CSV dataset workflows. It is most useful when you know the market shape you need, such as active BTC/USDT linear perpetuals or Deribit BTC options available during a historical replay window, but do not want to hardcode every exchange's symbol format.

Instrument fields such as symbol IDs, trading status, currencies, tick sizes, listing time, expiry and underlying asset class are sourced from exchange metadata APIs and normalized by Tardis where needed. `availableSince`, `availableTo` and `datasetId` are Tardis-side availability fields: when a symbol has appeared in exported metadata they reflect exported symbol state, while newly discovered active instruments can appear before replay or CSV dataset availability has caught up.

{% hint style="info" %}
Most Instruments Metadata API requests require an active [pro or business](/faq/billing-and-subscriptions.md#what-are-the-differences-between-subscription-types) subscription. BitMEX metadata is available without an API key for quick testing.
{% endhint %}

## Authorization

Provide the `Authorization` header with your API key:

```http
Authorization: Bearer YOUR_API_KEY
```

## Get one instrument

Returns one instrument for the provided exchange and symbol.

Use the `id` returned by the list endpoint as the symbol path segment. URL-encode the symbol when constructing URLs manually, especially for symbols that contain `/`, `:` or other reserved characters. The lookup is case-insensitive for the canonical symbol ID, while the response returns the exchange API symbol casing.

### Endpoint URL

<https://api.tardis.dev/v1/instruments/:exchange/:symbol_id>

### Example URLs

* <https://api.tardis.dev/v1/instruments/bitmex/XBTUSD>
* <https://api.tardis.dev/v1/instruments/okex-swap/BTC-USDT-SWAP>

### Response Format

{% hint style="info" %}
`changes` is complete only for `contractMultiplier` updates that we track from exchange announcements. Other changed fields are included on a best-effort basis and may not cover every historical change.
{% endhint %}

```typescript
{
	id: string // exchange-native symbol id, returned in exchange API casing
	datasetId?: string // CSV dataset symbol id; present after the symbol appears in exported dataset metadata
	exchange: string // exchange id
	baseCurrency: string // normalized, so for example bitmex XBTUSD has base currency set to BTC not XBT
	quoteCurrency: string // normalized, so for example bitfinex BTCUST has quote currency set to USDT, not UST
	type: InstrumentType
	contractType?: ContractType // only for derivatives, detailed contract type
	active: boolean // exchange-reported current trading status
	availableSince: string // Tardis metadata availability day; may differ from exchange listing time and dataset availability
	availableTo?: string // last UTC Tardis availability boundary, when known
	listing?: string // exchange listing timestamp in ISO format, if known
	expiry?: string // in ISO format, only for futures and options
	expirationType?: 'daily' | 'weekly' | 'next_week' | 'quarter' | 'next_quarter' // expiration schedule type
	underlyingIndex?: string // the underlying index for derivatives
	underlyingType?: UnderlyingType // underlying asset class; omitted for options and predictions
	priceIncrement: number // price tick size, price precision can be calculated from it
	amountIncrement: number // amount tick size, amount/size precision can be calculated from it
	minTradeAmount: number // min order size
	minNotional?: number // minimum order notional value, when separately exposed by the exchange
	makerFee: number // consider it as illustrative only, as it depends in practice on account traded volume levels, different categories, VIP levels, owning exchange currency etc
	takerFee: number // consider it as illustrative only, as it depends in practice on account traded volume levels, different categories, VIP levels, owning exchange currency etc
	inverse?: boolean // only for derivatives
	contractMultiplier?: number // only for derivatives
	quanto?: boolean // set to true for quanto instruments, otherwise undefined
	settlementCurrency?: string // settlement currency, only for quanto instruments as it has different base/quote currency
	strikePrice?: number // strike price, only for options
	optionType?: 'call' | 'put' // option type, only for options
	marginMode?: 'isolated' | 'cross' // margin mode
	margin?: boolean // whether margin trading is supported (spot)
	aliasFor?: string // if this instrument is an alias for another

	changes?: {
		until: string // date in ISO format
		priceIncrement?: number
		amountIncrement?: number
		contractMultiplier?: number
		minTradeAmount?: number
		minNotional?: number
		makerFee?: number
		takerFee?: number
		quanto?: boolean
		inverse?: boolean
		settlementCurrency?: string
		underlyingIndex?: string
		underlyingType?: UnderlyingType
		contractType?: ContractType
		expiry?: string
		quoteCurrency?: string
		type?: string
	}[]
}

// where InstrumentType is one of:
type InstrumentType =
	| "spot" | "perpetual" | "future" | "option" | "combo" | "prediction"

// where ContractType is one of:
type ContractType =
	| "move" | "linear_future" | "inverse_future" | "quanto_future"
	| "linear_perpetual" | "inverse_perpetual" | "quanto_perpetual"
	| "put_option" | "call_option" | "turbo_put_option" | "turbo_call_option"
	| "spread" | "interest_rate_swap" | "repo" | "index"
	| "linear_xperp" | "inverse_xperp"

// where UnderlyingType is one of:
type UnderlyingType =
	| "native" | "equity" | "commodity" | "fixed_income"
	| "fx" | "index" | "pre_market"
```

{% hint style="info" %}
`underlyingType` is returned for active/current instruments that have an exchange-sourced underlying asset class. Crypto-native instruments default to `native`; exchange-sourced non-native classifications such as `equity`, `commodity`, `fx`, `index`, `fixed_income`, and `pre_market` are returned when available. Older historical or delisted instruments may not have `underlyingType`. Options omit `underlyingType` to keep large options metadata responses compact. Prediction instruments omit `underlyingType`.

`minNotional` is returned only when the exchange exposes a minimum order value or notional separately from minimum order quantity.
{% endhint %}

{% hint style="info" %}
**`changes` field semantics:**

* The `changes` array is sorted chronologically by `until` (ascending). Each entry records field values that were valid **before** the `until` date — i.e., the values changed at `until`.
* Only `contractMultiplier` changes are guaranteed to be accurate and complete (monitored from exchange announcements). Other field changes, including `priceIncrement`, `amountIncrement`, `underlyingType` and `expiry`, are tracked on a best-effort basis.
* Changes are filtered to the instrument's `availableSince`—`availableTo` range.
  {% endhint %}

{% hint style="info" %}
**Lifecycle field semantics:**

* `active` — reflects the exchange-reported current trading status. It does not guarantee that Tardis already has replay data, CSV datasets, or non-empty data for every channel and date.
* `availableSince` — the Tardis metadata availability day, not necessarily the exact exchange listing time. When the symbol has appeared in exported metadata, this reflects the first exported UTC day we know for the symbol. For newly discovered instruments that have not appeared in exported metadata yet, it can be metadata-only/provisional. Use `listing` for the exchange listing timestamp when available.
* `datasetId` — the CSV dataset symbol ID. It is omitted until the symbol appears in exported dataset metadata. Use its presence, or `/exchanges/:exchange` `datasets.symbols[]`, to identify symbols for direct CSV downloads. It does not guarantee that every data type or date has a non-empty CSV file.
* `availableTo` — the UTC boundary where the instrument stops being available in Tardis metadata or exported symbol state, such as after expiry or delisting. It is absent for instruments that are still available and may lag behind the actual exchange delisting.
* `expiry` — current exchange-provided contract expiry for futures and options. It is not the same as `availableTo`; when a changed value was observed, the previous value may be available in `changes[].expiry`.
* Some exchanges reuse symbol IDs or maintain alias/legacy symbols alongside active ones. Both may appear in metadata results — use `active` to distinguish currently tradable instruments.
  {% endhint %}

### Sample Response

```javascript
{
  "id": "XBTUSD",
  "datasetId": "XBTUSD",
  "exchange": "bitmex",
  "baseCurrency": "BTC",
  "quoteCurrency": "USD",
  "type": "perpetual",
  "active": true,
  "availableSince": "2019-03-30T00:00:00.000Z",
  "priceIncrement": 0.5,
  "amountIncrement": 1,
  "minTradeAmount": 1,
  "makerFee": -0.00025,
  "takerFee": 0.00075,
  "inverse": true,
  "contractType": "inverse_perpetual",
  "contractMultiplier": 1
}
```

## List and filter instruments

Returns instruments for one exchange, optionally narrowed by a URL-encoded JSON `filter` query parameter.

Use this endpoint to find symbols for replay, streaming, and historical availability checks. Broad unfiltered responses can be large for options-heavy exchanges, so prefer filters when you know the market you need.

### Endpoint URL

[https://api.tardis.dev/v1/instruments/:exchange?filter={filter\_payload}](https://api.tardis.dev/v1/instruments/:exchange?filter=%7Bfilter_payload%7D)

### Example URLs

* <https://api.tardis.dev/v1/instruments/bitmex>
* [https://api.tardis.dev/v1/instruments/okex-futures?filter={"baseCurrency":"BTC","active":true}](https://api.tardis.dev/v1/instruments/okex-futures?filter=%7B%22baseCurrency%22:%22BTC%22,%22active%22:true%7D)
* [https://api.tardis.dev/v1/instruments/bitmex?filter={"baseCurrency":"BTC","quoteCurrency":\["USD","USDT"\],"type":"perpetual"}](https://api.tardis.dev/v1/instruments/bitmex?filter=%7B%22baseCurrency%22:%22BTC%22,%22quoteCurrency%22:%5B%22USD%22,%22USDT%22%5D,%22type%22:%22perpetual%22%7D)
* [https://api.tardis.dev/v1/instruments/binance-futures?filter={"underlyingType":"commodity","type":"perpetual","active":true}](https://api.tardis.dev/v1/instruments/binance-futures?filter=%7B%22underlyingType%22:%22commodity%22,%22type%22:%22perpetual%22,%22active%22:true%7D)
* [https://api.tardis.dev/v1/instruments/deribit?filter={"baseCurrency":"BTC","type":"option","availableSince":"2024-01-01","availableTo":"2024-01-02"}](https://api.tardis.dev/v1/instruments/deribit?filter=%7B%22baseCurrency%22:%22BTC%22,%22type%22:%22option%22,%22availableSince%22:%222024-01-01%22,%22availableTo%22:%222024-01-02%22%7D)

### Optional Filter Object

Provide `filter` as a JSON object. When used in a query string, it must be URL-encoded.

```typescript
{
	baseCurrency: string | string[] | undefined // normalized base currency, e.g. BTC
	quoteCurrency: string | string[] | undefined // normalized quote currency, e.g. USDT
	type: InstrumentType | InstrumentType[] | undefined
	contractType: ContractType | ContractType[] | undefined
	underlyingType: UnderlyingType | UnderlyingType[] | undefined
	active: boolean | undefined // true for currently tradable instruments, false for inactive instruments
	availableSince: string | undefined // UTC collection day; include instruments available at or after this day
	availableTo: string | undefined // UTC collection day boundary; with availableSince, include instruments whose availability overlaps the interval
}
```

{% hint style="info" %}
**Availability filters:**

* `availableSince` alone returns instruments whose Tardis availability reaches this UTC day or any later day.
* `availableTo` alone returns instruments available on that UTC day.
* `availableSince` and `availableTo` together return instruments whose Tardis availability overlaps the requested UTC-day interval. Use this for historical replay windows. The interval end is exclusive.
* The returned `availableTo` field is still the instrument's collection end date. It is not a simple "ended before" filter.
* When you need confirmed raw replay symbols or CSV dataset symbols, check [Exchange details](/api/http-api-reference.md#exchanges-exchange): use `availableSymbols` for raw replay and `datasets.symbols` for CSV downloads.
  {% endhint %}

### Filter Limits

* Each array filter accepts up to 50 values.
* String filter values must be between 1 and 150 characters.
* `type`, `contractType`, and `underlyingType` must use the allowed enum values documented above.
* The full request URL must be 12000 characters or shorter.

### Sample Request in JavaScript

```javascript
const filter = {
  baseCurrency: 'BTC',
  quoteCurrency: ['USD', 'USDT'],
  type: 'perpetual'
}

const headers = {
  Authorization: 'Bearer YOUR_API_KEY'
}

const url = new URL('https://api.tardis.dev/v1/instruments/bitmex')
url.searchParams.set('filter', JSON.stringify(filter))

const response = await fetch(url, { headers })
const instruments = await response.json()
```

### Response Format

Array of instruments objects as described for single instrument endpoint

## Client helpers for symbol discovery

Client helpers find exchange-specific instrument symbol IDs from normalized market criteria, so you do not have to hardcode each exchange's symbol format. They use the Instruments Metadata API to return the correct `id` for each requested exchange, ready to pass to replay, streaming, or raw data feeds.

Returned `id` symbols are exchange-provided IDs and are not normalized by the clients. Returned `datasetId` symbols are CSV dataset IDs for instruments whose symbols appear in exported dataset metadata; official clients URL-encode them when downloading datasets. If you construct dataset URLs manually, URL-encode the symbol path segment.

{% tabs %}
{% tab title="Node.js" %}
Find active BTC/USDT linear perpetuals across exchanges with different native symbol formats.

```javascript
import { findInstrumentSymbols, init } from 'tardis-dev'

init({ apiKey: 'YOUR_API_KEY' })

const symbolsByExchange = await findInstrumentSymbols(['bitmex', 'binance-futures', 'okex-swap', 'bybit'], {
  baseCurrency: 'BTC',
  quoteCurrency: 'USDT',
  contractType: 'linear_perpetual',
  active: true
})

console.log(symbolsByExchange)
// [
//   { exchange: 'bitmex', symbols: ['XBTUSDT'] },
//   { exchange: 'binance-futures', symbols: ['btcusdt'] },
//   { exchange: 'okex-swap', symbols: ['BTC-USDT-SWAP'] },
//   { exchange: 'bybit', symbols: ['BTCUSDT'] }
// ]
```

Find active Tesla equity instruments by filtering on `underlyingType`.

```javascript
const teslaEquitySymbols = await findInstrumentSymbols(
  ['binance-futures', 'okex-swap', 'coinbase-international', 'bybit', 'bitget-futures'],
  {
    baseCurrency: 'TSLA',
    underlyingType: 'equity',
    active: true
  }
)

console.log(teslaEquitySymbols)
// [
//   { exchange: 'binance-futures', symbols: ['tslausdt'] },
//   { exchange: 'okex-swap', symbols: ['TSLA-USDT-SWAP'] },
//   { exchange: 'coinbase-international', symbols: ['TSLA-PERP'] },
//   { exchange: 'bybit', symbols: ['TSLAUSDT'] },
//   { exchange: 'bitget-futures', symbols: ['TSLAUSDT'] }
// ]
```

Use the `datasetId` selector only when you need symbols for direct CSV dataset file downloads. Instruments without `datasetId` are omitted from selector results.

```javascript
const csvSymbolsByExchange = await findInstrumentSymbols(
  ['bitmex', 'binance-futures', 'okex-swap', 'bybit'],
  {
    baseCurrency: 'BTC',
    quoteCurrency: 'USDT',
    contractType: 'linear_perpetual',
    active: true
  },
  'datasetId'
)
```

{% endtab %}

{% tab title="Python" %}
Find active BTC/USDT linear perpetuals across exchanges with different native symbol formats.

```python
from tardis_dev import find_instrument_symbols

symbols_by_exchange = find_instrument_symbols(
    ["bitmex", "binance-futures", "okex-swap", "bybit"],
    {
        "baseCurrency": "BTC",
        "quoteCurrency": "USDT",
        "contractType": "linear_perpetual",
        "active": True,
    },
    api_key="YOUR_API_KEY",
)

print(symbols_by_exchange)
# [
#   {"exchange": "bitmex", "symbols": ["XBTUSDT"]},
#   {"exchange": "binance-futures", "symbols": ["btcusdt"]},
#   {"exchange": "okex-swap", "symbols": ["BTC-USDT-SWAP"]},
#   {"exchange": "bybit", "symbols": ["BTCUSDT"]},
# ]
```

Find active Tesla equity instruments by filtering on `underlyingType`.

```python
tesla_equity_symbols = find_instrument_symbols(
    ["binance-futures", "okex-swap", "coinbase-international", "bybit", "bitget-futures"],
    {
        "baseCurrency": "TSLA",
        "underlyingType": "equity",
        "active": True,
    },
    api_key="YOUR_API_KEY",
)

print(tesla_equity_symbols)
# [
#   {"exchange": "binance-futures", "symbols": ["tslausdt"]},
#   {"exchange": "okex-swap", "symbols": ["TSLA-USDT-SWAP"]},
#   {"exchange": "coinbase-international", "symbols": ["TSLA-PERP"]},
#   {"exchange": "bybit", "symbols": ["TSLAUSDT"]},
#   {"exchange": "bitget-futures", "symbols": ["TSLAUSDT"]},
# ]
```

Use `selector="datasetId"` only when you need symbols for direct CSV dataset file downloads. Instruments without `datasetId` are omitted from selector results.

```python
from tardis_dev import find_instrument_symbols_async

csv_symbols_by_exchange = await find_instrument_symbols_async(
    ["bitmex", "binance-futures", "okex-swap", "bybit"],
    {
        "baseCurrency": "BTC",
        "quoteCurrency": "USDT",
        "contractType": "linear_perpetual",
        "active": True,
    },
    selector="datasetId",
    api_key="YOUR_API_KEY",
)
```

{% endtab %}
{% endtabs %}


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation dynamically by asking a question.

Perform an HTTP GET request on the current page URL with the `ask` query parameter, and the optional `goal` query parameter:

```
GET https://docs.tardis.dev/api/instruments-metadata-api.md?ask=<question>&goal=<endgoal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is optional and describes the broader end goal you are ultimately trying to accomplish on behalf of the user. GitBook uses it to tailor the answer towards what is most useful for that goal.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
