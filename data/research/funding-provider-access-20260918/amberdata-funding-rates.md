> ## Documentation Index
> Fetch the complete documentation index at: https://docs.amberdata.io/llms.txt
> Use this file to discover all available pages before exploring further.

# Historical

> Provides historical funding rate data for futures instruments, including timestamps, actual and projected rates, and details on upcoming funding times across exchanges.

<Warning>
  The maximum time range (difference between `startDate` and `endDate`) is **731 days (2 years)**.
</Warning>

<Note>
  If the startDate and endDate query parameters are not provided, the API will return the data from the previous 24 hours at the tick granularity.
</Note>


## OpenAPI

````yaml get /futures/funding-rates/{instrument}
openapi: 3.1.0
info:
  title: market-api
  version: '2'
servers:
  - url: https://api.amberdata.com/markets
security:
  - ApiKeyAuth: []
paths:
  /futures/funding-rates/{instrument}:
    get:
      summary: Historical
      description: >-
        Provides historical funding rate data for futures instruments, including
        timestamps, actual and projected rates, and details on upcoming funding
        times across exchanges.
      operationId: futures-funding-rates-historical
      parameters:
        - name: exchange
          in: query
          description: >-
            The exchange for which data should be retrieved. Only **1** exchange
            is allowed.
          required: true
          schema:
            type: string
            default: binance
        - name: instrument
          in: path
          description: The futures instrument for which data will be retrieved.
          schema:
            type: string
            default: BTCUSD_PERP
          required: true
        - name: startDate
          in: query
          description: >-
            **[Optional]** Payload only includes data after this date
            (inclusive). **[Formats]** `seconds | milliseconds | iso8601`
            **[Examples]** `1578531600 | 1578531600000 | 2020-09-01T01:00:00`
          schema:
            type: string
            format: date-time
        - name: endDate
          in: query
          description: >-
            **[Optional]** Payload only includes data before this date
            (exclusive). **[Formats]** `seconds | milliseconds | iso8601`
            **[Examples]** `1578531600 | 1578531600000 | 2020-09-01T01:00:00`
          schema:
            type: string
            format: date-time
        - name: timeFormat
          in: query
          description: '**[Optional]** Time format of the timestamps in the return payload.'
          schema:
            type: string
            enum:
              - milliseconds
              - ms*
              - iso
              - iso8601
              - hr
              - human_readable
            default: hr
        - name: sortDirection
          in: query
          description: >-
            **[Optional]** Specifies the direction in which the data is sorted
            (by timestamp).   **[Defaults]** asc (ascending order).   **[Usage
            Conditions]** This parameter can only be used if the `startDate` and
            `endDate` timeframe is within the most recent 24 hours, or if the
            `startDate` and `endDate` parameters are not used at all.  
            **[Examples]** ascending | descending | asc | desc
          schema:
            type: string
        - name: rateType
          in: query
          description: >-
            **`applied`**: Returns only applied funding rates (historical,
            confirmed rates) **`predicted`**: Returns only predicted funding
            rates (future, expected rates) **`both`** (default): Returns both
            predicted and applied funding rates
          schema:
            type: string
        - name: Accept-Encoding
          in: header
          required: true
          description: ''
          schema:
            type: string
            default: gzip, deflate, br
        - name: api-version
          in: header
          schema:
            type: string
      responses:
        '200':
          description: '200'
          content:
            application/json:
              examples:
                Result:
                  value:
                    status: 200
                    title: OK
                    description: Successful request
                    payload:
                      metadata:
                        next: null
                        api-version: '2023-09-30'
                      data:
                        - instrument: BTCUSD_PERP
                          exchange: binance
                          exchangeTimestamp: 1717545600000
                          exchangeTimestampNanoseconds: 0
                          fundingInterval: null
                          fundingRate: 0.0001
                          nextFundingRate: null
                          nextFundingTime: null
                          isActualFundingRate: true
                        - instrument: BTCUSD_PERP
                          exchange: binance
                          exchangeTimestamp: 1717545601000
                          exchangeTimestampNanoseconds: 0
                          fundingInterval: null
                          fundingRate: 0.0001
                          nextFundingRate: null
                          nextFundingTime: 1717574400000
                          isActualFundingRate: false
              schema:
                type: object
                properties:
                  status:
                    type: integer
                  title:
                    type: string
                  description:
                    type: string
                  payload:
                    type: object
                    properties:
                      metadata:
                        type: object
                        properties:
                          next:
                            type: string
                          api-version:
                            type: string
                      data:
                        type: array
                        items:
                          type: object
                          properties:
                            instrument:
                              type: string
                            exchange:
                              type: string
                            exchangeTimestamp:
                              type: integer
                            exchangeTimestampNanoseconds:
                              type: integer
                            fundingInterval:
                              type: number
                            fundingRate:
                              type: number
                            nextFundingRate:
                              type: number
                            nextFundingTime:
                              type: number
                            isActualFundingRate:
                              type: boolean
        '400':
          description: '400'
          content:
            application/json:
              examples:
                Result:
                  value: '{}'
              schema:
                type: object
                properties: {}
      deprecated: false
      security:
        - ApiKeyAuth: []
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: x-api-key

````