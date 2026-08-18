-- Inventory Analytics Portfolio Project
-- Author: Ravindra Kadiri
-- Database: PostgreSQL
--
-- This file contains the core analysis queries for:
-- products, vendors, warehouses, inventory, sales,
-- purchases, orders and GRN data.

-- ============================================================
-- 1. DATA QUALITY CHECKS
-- ============================================================

-- Duplicate product IDs
SELECT product_id, COUNT(*) AS duplicate_count
FROM products
GROUP BY product_id
HAVING COUNT(*) > 1;

-- Negative inventory quantities
SELECT *
FROM inventory
WHERE stock_qty < 0
   OR reserved_qty < 0
   OR damaged_qty < 0;

-- Sales records without a matching product
SELECT s.*
FROM sales s
LEFT JOIN products p ON s.product_id = p.product_id
WHERE p.product_id IS NULL;

-- Purchases without a matching vendor
SELECT pu.*
FROM purchases pu
LEFT JOIN vendors v ON pu.vendor_id = v.vendor_id
WHERE v.vendor_id IS NULL;

-- ============================================================
-- 2. OVERALL INVENTORY KPI
-- ============================================================

SELECT
    COUNT(DISTINCT product_id) AS products_in_inventory,
    COUNT(DISTINCT warehouse_id) AS active_warehouses,
    SUM(stock_qty) AS total_stock_units,
    SUM(reserved_qty) AS total_reserved_units,
    SUM(damaged_qty) AS total_damaged_units,
    ROUND(SUM(stock_qty * unit_cost), 2) AS inventory_value
FROM inventory;

-- ============================================================
-- 3. INVENTORY VALUE BY WAREHOUSE
-- ============================================================

SELECT
    i.warehouse_id,
    w.warehouse_name,
    SUM(i.stock_qty) AS stock_units,
    ROUND(SUM(i.stock_qty * i.unit_cost), 2) AS inventory_value
FROM inventory i
LEFT JOIN warehouses w
    ON i.warehouse_id = w.warehouse_id
GROUP BY i.warehouse_id, w.warehouse_name
ORDER BY inventory_value DESC;

-- ============================================================
-- 4. TOP PRODUCTS BY INVENTORY VALUE
-- ============================================================

SELECT
    i.product_id,
    p.product_name,
    p.category,
    SUM(i.stock_qty) AS stock_units,
    ROUND(SUM(i.stock_qty * i.unit_cost), 2) AS inventory_value
FROM inventory i
LEFT JOIN products p
    ON i.product_id = p.product_id
GROUP BY i.product_id, p.product_name, p.category
ORDER BY inventory_value DESC
LIMIT 20;

-- ============================================================
-- 5. LOW STOCK / REORDER ALERTS
-- ============================================================

SELECT
    i.product_id,
    p.product_name,
    i.warehouse_id,
    i.stock_qty,
    p.reorder_level,
    CASE
        WHEN i.stock_qty = 0 THEN 'OUT OF STOCK'
        WHEN i.stock_qty <= p.reorder_level THEN 'REORDER'
        ELSE 'HEALTHY'
    END AS stock_status
FROM inventory i
JOIN products p
    ON i.product_id = p.product_id
WHERE i.stock_qty <= p.reorder_level
ORDER BY i.stock_qty ASC;

-- ============================================================
-- 6. MONTHLY SALES PERFORMANCE
-- ============================================================

SELECT
    DATE_TRUNC('month', sale_date)::DATE AS sales_month,
    SUM(quantity) AS units_sold,
    ROUND(SUM(quantity * unit_price - COALESCE(discount, 0)), 2) AS net_sales
FROM sales
GROUP BY DATE_TRUNC('month', sale_date)
ORDER BY sales_month;

-- ============================================================
-- 7. TOP PRODUCTS BY SALES
-- ============================================================

SELECT
    s.product_id,
    p.product_name,
    p.category,
    SUM(s.quantity) AS units_sold,
    ROUND(SUM(s.quantity * s.unit_price - COALESCE(s.discount, 0)), 2) AS net_sales
FROM sales s
LEFT JOIN products p
    ON s.product_id = p.product_id
GROUP BY s.product_id, p.product_name, p.category
ORDER BY net_sales DESC
LIMIT 20;

-- ============================================================
-- 8. PURCHASE ANALYSIS BY VENDOR
-- ============================================================

SELECT
    pu.vendor_id,
    v.vendor_name,
    COUNT(DISTINCT pu.purchase_id) AS purchase_orders,
    SUM(pu.quantity) AS units_purchased,
    ROUND(SUM(pu.quantity * pu.unit_cost), 2) AS purchase_value,
    ROUND(AVG(v.lead_time_days), 1) AS avg_lead_time_days
FROM purchases pu
LEFT JOIN vendors v
    ON pu.vendor_id = v.vendor_id
GROUP BY pu.vendor_id, v.vendor_name
ORDER BY purchase_value DESC;

-- ============================================================
-- 9. GRN QUALITY / REJECTION RATE
-- ============================================================

SELECT
    warehouse_id,
    SUM(received_qty) AS received_units,
    SUM(accepted_qty) AS accepted_units,
    SUM(rejected_qty) AS rejected_units,
    ROUND(
        100.0 * SUM(rejected_qty) / NULLIF(SUM(received_qty), 0),
        2
    ) AS rejection_rate_pct
FROM grn
GROUP BY warehouse_id
ORDER BY rejection_rate_pct DESC;

-- ============================================================
-- 10. ORDER FULFILLMENT
-- ============================================================

SELECT
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE order_status = 'Delivered') AS delivered_orders,
    COUNT(*) FILTER (WHERE order_status <> 'Delivered') AS open_or_failed_orders,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE order_status = 'Delivered')
        / NULLIF(COUNT(*), 0),
        2
    ) AS fulfillment_rate_pct
FROM orders;

-- ============================================================
-- 11. ON-TIME DELIVERY BY WAREHOUSE
-- ============================================================

SELECT
    warehouse_id,
    COUNT(*) AS delivered_orders,
    ROUND(AVG(delivered_date - order_date), 2) AS avg_delivery_days,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE delivered_date <= promised_date)
        / NULLIF(COUNT(*), 0),
        2
    ) AS on_time_delivery_pct
FROM orders
WHERE delivered_date IS NOT NULL
GROUP BY warehouse_id
ORDER BY on_time_delivery_pct DESC;

-- ============================================================
-- 12. SLOW-MOVING / NO-SALES INVENTORY
-- ============================================================

SELECT
    i.product_id,
    p.product_name,
    i.warehouse_id,
    i.stock_qty,
    ROUND(i.stock_qty * i.unit_cost, 2) AS blocked_inventory_value
FROM inventory i
JOIN products p
    ON i.product_id = p.product_id
LEFT JOIN sales s
    ON i.product_id = s.product_id
   AND i.warehouse_id = s.warehouse_id
WHERE s.product_id IS NULL
ORDER BY blocked_inventory_value DESC;

-- ============================================================
-- 13. INVENTORY AGE BUCKET
-- ============================================================

SELECT
    i.product_id,
    p.product_name,
    i.warehouse_id,
    i.stock_qty,
    i.last_grn_date,
    CURRENT_DATE - i.last_grn_date AS inventory_age_days,
    CASE
        WHEN CURRENT_DATE - i.last_grn_date <= 30 THEN '0-30 Days'
        WHEN CURRENT_DATE - i.last_grn_date <= 60 THEN '31-60 Days'
        WHEN CURRENT_DATE - i.last_grn_date <= 90 THEN '61-90 Days'
        ELSE '90+ Days'
    END AS age_bucket,
    ROUND(i.stock_qty * i.unit_cost, 2) AS inventory_value
FROM inventory i
LEFT JOIN products p
    ON i.product_id = p.product_id
WHERE i.last_grn_date IS NOT NULL
ORDER BY inventory_age_days DESC;

-- ============================================================
-- 14. EXPIRING INVENTORY
-- ============================================================

SELECT
    i.product_id,
    p.product_name,
    i.warehouse_id,
    i.stock_qty,
    i.expiry_date,
    i.expiry_date - CURRENT_DATE AS days_to_expiry,
    ROUND(i.stock_qty * i.unit_cost, 2) AS inventory_value
FROM inventory i
LEFT JOIN products p
    ON i.product_id = p.product_id
WHERE i.expiry_date IS NOT NULL
  AND i.expiry_date >= CURRENT_DATE
  AND i.expiry_date <= CURRENT_DATE + INTERVAL '30 days'
ORDER BY days_to_expiry ASC;

-- ============================================================
-- 15. INVENTORY TURNOVER APPROXIMATION
-- ============================================================

WITH sales_value AS (
    SELECT
        product_id,
        SUM(quantity * unit_price) AS sales_value
    FROM sales
    GROUP BY product_id
),
inventory_value AS (
    SELECT
        product_id,
        SUM(stock_qty * unit_cost) AS inventory_value
    FROM inventory
    GROUP BY product_id
)
SELECT
    p.product_id,
    p.product_name,
    COALESCE(sv.sales_value, 0) AS sales_value,
    COALESCE(iv.inventory_value, 0) AS inventory_value,
    ROUND(
        COALESCE(sv.sales_value, 0) / NULLIF(iv.inventory_value, 0),
        2
    ) AS inventory_turnover_ratio
FROM products p
LEFT JOIN sales_value sv ON p.product_id = sv.product_id
LEFT JOIN inventory_value iv ON p.product_id = iv.product_id
ORDER BY inventory_turnover_ratio DESC NULLS LAST;

-- ============================================================
-- 16. EXECUTIVE SUMMARY
-- ============================================================

SELECT
    (SELECT COUNT(*) FROM products) AS total_products,
    (SELECT COUNT(*) FROM warehouses) AS total_warehouses,
    (SELECT COALESCE(SUM(stock_qty), 0) FROM inventory) AS stock_units,
    (SELECT ROUND(COALESCE(SUM(stock_qty * unit_cost), 0), 2)
     FROM inventory) AS inventory_value,
    (SELECT COALESCE(SUM(quantity), 0) FROM sales) AS units_sold,
    (SELECT ROUND(COALESCE(SUM(quantity * unit_price - COALESCE(discount, 0)), 0), 2)
     FROM sales) AS net_sales;
