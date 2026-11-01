# Data audit and cleaning log

Every check run before analysis, what it found, and what was decided.

| # | Check | Finding | Decision |
|---|---|---|---|
| 1 | Duplicate order_id in orders | 0 duplicates | none needed |
| 2 | Orders without items | 775 orders (99% are unavailable/canceled) | kept in order table, flagged has_items=False, revenue = 0 |
| 3 | Delivered orders with no delivery date | 8 orders | excluded from delivery-time metrics only |
| 4 | Delivery date before purchase date | 0 orders | none needed |
| 5 | Orders with more than one review | 551 extra review rows | keep the latest review per order |
| 6 | Products with no category | 610 products | labelled 'unknown' |
| 7 | Categories with no English name | 2: ['pc_gamer', 'portateis_cozinha_e_preparadores_de_alimentos'] | keep the Portuguese name |
| 8 | Item prices <= 0 | 0 items | none needed |
| 9 | Extreme item prices | max = 6,735 (99.9th pct = 2,110) | kept: real high-value items, reported as median where it matters |
| 10 | customer_id vs customer_unique_id | 99,441 customer_id but 96,096 real people | use customer_unique_id to count repeat buyers |
| 11 | Months with very few orders | 2016-09 (4), 2016-10 (324), 2016-12 (1), 2018-09 (16), 2018-10 (4) | trends limited to 2017-01 .. 2018-08 |
| 12 | Orders kept after window filter | 99,092 of 99,441 | analysis table |
