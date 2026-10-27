# Memory search parity: FTS5 against Postgres

Generated 2026-10-26T20:43:42 by `tools/memory_search_parity.py`.

* corpus: **7889** memories, snapshotted from the live lucent store and loaded into a scratch Postgres database this script created and dropped
* queries: **10** real ones, each embedded once and handed to both engines, so any difference below is a difference in the search
* identical top-5 **in the same order**: **4/10**
* mean overlap in the top 5: **88%**
* largest disagreement on a shared row's cosine: **0.00e+00**

Cosine is the half that can be expected to agree exactly, and the figure above says it does to well inside the four decimal places the response rounds to. The keyword half cannot agree exactly: Postgres has no BM25, so `ts_rank` is a different formula rescaled into the range the surrounding arithmetic was written against. Where the two answers differ, it is that half moving.

### `rotation threshold for a terminal pane`

* overlap in the top 5: 4/5

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 4560 | bm25 | 3921 | bm25 |  |

### `which voice engine speaks a mind`

* overlap in the top 5: 4/5

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 7026 | bm25 | 7003 | bm25 |  |

### `postgres migration one database`

* overlap in the top 5: 4/5

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 8047 | bm25 | 575 | bm25 |  |

### `surface claim who a bot answers`

* overlap in the top 5: 5/5 — same order

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 7951 | bm25 | 7951 | bm25 | yes |

### `left elbow tendinopathy reloading`

* overlap in the top 5: 5/5 — same order

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 8065 | bm25 | 8065 | bm25 | yes |

### `restart the comms container`

* overlap in the top 5: 4/5

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 3885 | bm25 | 7126 | bm25 |  |

### `what did Daniel decide about Zeek output`

* overlap in the top 5: 4/5

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 8183 | bm25 | 734 | bm25 |  |

### `the and of is are to be`

* overlap in the top 5: 5/5 — same order

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 7360 | fill | 7360 | fill | yes |

### `lunch with Jose`

* overlap in the top 5: 5/5 — same order

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 3047 | bm25 | 3047 | bm25 | yes |

### `rotating a session`

* overlap in the top 5: 4/5

| rank | lucent (FTS5) | bucket | Postgres | bucket | cosine agrees |
|---|---|---|---|---|---|
| 1 | 7518 | recency | 7518 | recency | yes |
| 2 | 7537 | recency | 7537 | recency | yes |
| 3 | 4459 | recency | 4459 | recency | yes |
| 4 | 4680 | cosine | 4680 | cosine | yes |
| 5 | 1841 | bm25 | 528 | bm25 |  |
