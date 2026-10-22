# ADR-002 — Wikidata access: identified, rate-limited, cached per entity

**Status:** accepted · **Evidence:** Wikimedia policy and reproducibility (no benchmark).

## Context

The pipeline queries Wikidata live: two search APIs, `wbgetentities` and the SPARQL endpoint. A full evaluation made 1,464 HTTP requests, on a cache already warmed by the dev runs. Wikidata keeps changing, so results computed against the live service drift over time.

## Decision

- **Identification.** Every request sends a descriptive `User-Agent` with a contact address, as the [Wikimedia User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy) requires.
- **Rate.** At most **150 requests per minute**, spaced evenly, with **3 requests in parallel** at most. The gateway allows 200 per minute to clients identified by User-Agent only ([rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)).
- **Errors.** On 429 or 5xx, the client waits for `Retry-After`, or uses exponential backoff from 5 s, and retries up to 4 times.
- **No `maxlag`.** The client is read-only. On wikidata.org, `maxlag` tracks query-service replication lag, so it would block reads for reasons that have nothing to do with us.
- **Cache per entity.** Each search query, each entity's terms, types and relations are stored in their own JSON file. A cached batch response would be invalidated as soon as the batch composition changed.
- **Offline mode.** `--offline` turns any cache miss into an error, so an evaluation provably runs on the cached snapshot.
- **Batching.** `wbgetentities` is called with 50 IDs per request, its maximum; SPARQL with 100 QIDs per `VALUES` clause.

## Why no benchmark

Measuring the throughput limit would mean deliberately hitting 429 errors on a shared public service, which the etiquette asks clients not to do. The limit is documented, so we stay below it rather than measure it.

The cache changes no result: it makes runs repeatable and fast. The full evaluation took 1,483 s with network fetches (1,464 HTTP calls) and 199 s offline from the cache (0 calls, 54,424 cache hits on entity terms).

## Consequences

- The rate limit dominates a run with network fetches (about 25 minutes). An offline run takes about 3 minutes, mostly spaCy and the embeddings.
- Results are tied to the Wikidata snapshot in the cache (October 2026). Shipping the cache would let a reviewer reproduce every number exactly.
