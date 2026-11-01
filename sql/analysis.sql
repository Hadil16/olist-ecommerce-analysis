-- Olist e-commerce analysis: the core business questions in SQL (SQLite).
-- Run against data/olist.db (built by load_data.py).
-- Definitions: revenue = item prices of DELIVERED orders, freight excluded.
--              analysis window = purchases from 2017-01-01 to 2018-08-31.

-- ---------------------------------------------------------------
-- Q0. Data audit: orders that have no items, by status
-- ---------------------------------------------------------------
SELECT o.order_status, COUNT(*) AS orders_without_items
FROM orders o
LEFT JOIN order_items oi ON o.order_id = oi.order_id
WHERE oi.order_id IS NULL
GROUP BY o.order_status
ORDER BY orders_without_items DESC;

-- ---------------------------------------------------------------
-- Q1. How do revenue and orders evolve month by month?
-- ---------------------------------------------------------------
SELECT substr(o.order_purchase_timestamp, 1, 7) AS month,
       COUNT(DISTINCT o.order_id)               AS orders,
       ROUND(SUM(oi.price), 2)                  AS revenue,
       ROUND(SUM(oi.price) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01'
GROUP BY month
ORDER BY month;

-- ---------------------------------------------------------------
-- Q2. Which product categories bring the most revenue?
-- ---------------------------------------------------------------
SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
       ROUND(SUM(oi.price), 2) AS revenue,
       ROUND(100.0 * SUM(oi.price) / SUM(SUM(oi.price)) OVER (), 1) AS pct_of_revenue
FROM order_items oi
JOIN orders o   ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01'
GROUP BY category
ORDER BY revenue DESC
LIMIT 10;

-- ---------------------------------------------------------------
-- Q3. Where do customers live? Revenue share by state
-- ---------------------------------------------------------------
SELECT c.customer_state,
       ROUND(SUM(oi.price), 2) AS revenue,
       ROUND(100.0 * SUM(oi.price) / SUM(SUM(oi.price)) OVER (), 1) AS pct_of_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01'
GROUP BY c.customer_state
ORDER BY revenue DESC
LIMIT 10;

-- ---------------------------------------------------------------
-- Q4. How often are orders delivered after the promised date?
-- ---------------------------------------------------------------
SELECT COUNT(*) AS delivered_orders,
       ROUND(100.0 * AVG(order_delivered_customer_date > order_estimated_delivery_date), 1) AS pct_late
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
  AND order_purchase_timestamp >= '2017-01-01'
  AND order_purchase_timestamp <  '2018-09-01';

-- ---------------------------------------------------------------
-- Q5. Do late deliveries get worse reviews?
-- Uses the latest review per order (551 orders have more than one).
-- ---------------------------------------------------------------
WITH latest_review AS (
    SELECT order_id, review_score,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) AS rn
    FROM reviews
)
SELECT CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
            THEN 'late' ELSE 'on time' END AS delivery,
       COUNT(*)                                   AS reviewed_orders,
       ROUND(AVG(r.review_score), 2)              AS avg_review_score,
       ROUND(100.0 * AVG(r.review_score = 1), 1)  AS pct_one_star
FROM orders o
JOIN latest_review r ON r.order_id = o.order_id AND r.rn = 1
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01'
GROUP BY delivery;

-- ---------------------------------------------------------------
-- Q6. How many customers buy more than once?
-- customer_id changes with every order, so customer_unique_id identifies the person.
-- ---------------------------------------------------------------
WITH per_customer AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS orders
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= '2017-01-01'
      AND o.order_purchase_timestamp <  '2018-09-01'
    GROUP BY c.customer_unique_id
)
SELECT CASE WHEN orders = 1 THEN 'bought once' ELSE 'bought 2+ times' END AS segment,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_customers
FROM per_customer
GROUP BY segment;

-- ---------------------------------------------------------------
-- Q7. Which states have the worst delivery performance?
-- HAVING removes small states, because a late rate on 20 orders is noise.
-- ---------------------------------------------------------------
SELECT c.customer_state,
       COUNT(*) AS delivered_orders,
       ROUND(100.0 * AVG(o.order_delivered_customer_date > o.order_estimated_delivery_date), 1) AS pct_late,
       ROUND(AVG(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)), 1) AS avg_delivery_days
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01'
GROUP BY c.customer_state
HAVING COUNT(*) >= 500
ORDER BY pct_late DESC;

-- ---------------------------------------------------------------
-- Q8. Month-over-month revenue growth (window function LAG)
-- ---------------------------------------------------------------
WITH monthly AS (
    SELECT substr(o.order_purchase_timestamp, 1, 7) AS month,
           SUM(oi.price) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= '2017-01-01'
      AND o.order_purchase_timestamp <  '2018-09-01'
    GROUP BY month
)
SELECT month,
       ROUND(revenue, 0) AS revenue,
       ROUND(100.0 * (revenue / LAG(revenue) OVER (ORDER BY month) - 1), 1) AS mom_growth_pct
FROM monthly
ORDER BY month;
