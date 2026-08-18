"""
Inventory Analytics Portfolio Project
Author: Ravindra Kadiri

Loads the eight CSV files from ../data and produces portfolio-ready
inventory, sales, purchase, GRN and order analysis using pandas.

Expected data folder:
../data/
    grn.csv
    inventory.csv
    orders.csv
    products.csv
    purchases.csv
    sales.csv
    vendors.csv
    warehouses.csv

Run:
    python inventory_analysis.py

Output files are written to ./output/
"""

from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_csv(filename: str) -> pd.DataFrame:
    """Load a CSV and standardise column names."""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    df = pd.read_csv(path)
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )
    return df


def require_column(df: pd.DataFrame, column: str, table: str) -> None:
    if column not in df.columns:
        raise KeyError(
            f"Column '{column}' was not found in {table}. "
            f"Available columns: {list(df.columns)}"
        )


# ------------------------------------------------------------
# 1. LOAD ALL DATA
# ------------------------------------------------------------

files = {
    "grn": "grn.csv",
    "inventory": "inventory.csv",
    "orders": "orders.csv",
    "products": "products.csv",
    "purchases": "purchases.csv",
    "sales": "sales.csv",
    "vendors": "vendors.csv",
    "warehouses": "warehouses.csv",
}

data = {name: load_csv(filename) for name, filename in files.items()}

print("=" * 70)
print("INVENTORY ANALYTICS")
print("=" * 70)

for name, df in data.items():
    print(f"{name:12s}: {len(df):>8,} rows x {len(df.columns)} columns")


# ------------------------------------------------------------
# 2. STANDARDISE TYPES
# ------------------------------------------------------------

numeric_map = {
    "inventory": ["stock_qty", "reserved_qty", "damaged_qty", "unit_cost"],
    "sales": ["quantity", "unit_price", "discount"],
    "purchases": ["quantity", "unit_cost"],
    "orders": ["quantity"],
    "grn": ["received_qty", "accepted_qty", "rejected_qty"],
}

for table, columns in numeric_map.items():
    for column in columns:
        if column in data[table].columns:
            data[table][column] = pd.to_numeric(
                data[table][column], errors="coerce"
            )


date_map = {
    "inventory": ["expiry_date", "last_grn_date"],
    "sales": ["sale_date"],
    "purchases": ["purchase_date"],
    "orders": ["order_date", "promised_date", "delivered_date"],
    "grn": ["grn_date"],
}

for table, columns in date_map.items():
    for column in columns:
        if column in data[table].columns:
            data[table][column] = pd.to_datetime(
                data[table][column], errors="coerce"
            )


inventory = data["inventory"]
sales = data["sales"]
purchases = data["purchases"]
orders = data["orders"]
grns = data["grn"]
products = data["products"]

require_column(inventory, "product_id", "inventory")
require_column(inventory, "warehouse_id", "inventory")
require_column(inventory, "stock_qty", "inventory")
require_column(inventory, "unit_cost", "inventory")
require_column(sales, "product_id", "sales")
require_column(sales, "quantity", "sales")
require_column(sales, "unit_price", "sales")


# ------------------------------------------------------------
# 3. DATA QUALITY REPORT
# ------------------------------------------------------------

quality = []
for name, df in data.items():
    quality.append(
        {
            "table": name,
            "rows": len(df),
            "columns": len(df.columns),
            "missing_cells": int(df.isna().sum().sum()),
            "duplicate_rows": int(df.duplicated().sum()),
        }
    )

quality_report = pd.DataFrame(quality)
quality_report.to_csv(OUTPUT_DIR / "data_quality_report.csv", index=False)

print("\nDATA QUALITY")
print(quality_report.to_string(index=False))


# ------------------------------------------------------------
# 4. INVENTORY KPI
# ------------------------------------------------------------

inventory["inventory_value"] = (
    inventory["stock_qty"].fillna(0)
    * inventory["unit_cost"].fillna(0)
)

total_stock = inventory["stock_qty"].sum()
total_inventory_value = inventory["inventory_value"].sum()
reserved_units = inventory["reserved_qty"].sum() if "reserved_qty" in inventory else 0
damaged_units = inventory["damaged_qty"].sum() if "damaged_qty" in inventory else 0

inventory_kpi = pd.DataFrame(
    [{
        "total_stock_units": total_stock,
        "reserved_units": reserved_units,
        "damaged_units": damaged_units,
        "inventory_value": round(total_inventory_value, 2),
    }]
)

inventory_kpi.to_csv(OUTPUT_DIR / "inventory_kpi.csv", index=False)

print("\nINVENTORY KPI")
print(inventory_kpi.to_string(index=False))


# ------------------------------------------------------------
# 5. INVENTORY BY WAREHOUSE
# ------------------------------------------------------------

warehouse_inventory = (
    inventory.groupby("warehouse_id", as_index=False)
    .agg(
        stock_units=("stock_qty", "sum"),
        inventory_value=("inventory_value", "sum"),
        products=("product_id", "nunique"),
    )
    .sort_values("inventory_value", ascending=False)
)

warehouse_inventory.to_csv(
    OUTPUT_DIR / "inventory_by_warehouse.csv", index=False
)

print("\nINVENTORY BY WAREHOUSE")
print(warehouse_inventory.head(10).to_string(index=False))


# ------------------------------------------------------------
# 6. TOP PRODUCTS BY SALES
# ------------------------------------------------------------

sales["gross_sales"] = sales["quantity"].fillna(0) * sales["unit_price"].fillna(0)
if "discount" in sales.columns:
    sales["net_sales"] = sales["gross_sales"] - sales["discount"].fillna(0)
else:
    sales["net_sales"] = sales["gross_sales"]

product_sales = (
    sales.groupby("product_id", as_index=False)
    .agg(
        units_sold=("quantity", "sum"),
        net_sales=("net_sales", "sum"),
    )
    .sort_values("net_sales", ascending=False)
)

if "product_id" in products.columns and "product_name" in products.columns:
    product_sales = product_sales.merge(
        products[["product_id", "product_name"]],
        on="product_id",
        how="left",
    )

product_sales.to_csv(OUTPUT_DIR / "top_products_by_sales.csv", index=False)

print("\nTOP PRODUCTS BY SALES")
print(product_sales.head(10).to_string(index=False))


# ------------------------------------------------------------
# 7. LOW STOCK / REORDER ALERTS
# ------------------------------------------------------------

if "reorder_level" in products.columns:
    reorder = inventory.merge(
        products[["product_id", "product_name", "reorder_level"]],
        on="product_id",
        how="left",
    )

    reorder["stock_status"] = np.select(
        [
            reorder["stock_qty"] <= 0,
            reorder["stock_qty"] <= reorder["reorder_level"].fillna(np.inf),
        ],
        ["OUT OF STOCK", "REORDER"],
        default="HEALTHY",
    )

    reorder_alerts = reorder[
        reorder["stock_status"].isin(["OUT OF STOCK", "REORDER"])
    ].copy()

    reorder_alerts.to_csv(OUTPUT_DIR / "reorder_alerts.csv", index=False)

    print("\nREORDER ALERTS")
    print(
        reorder_alerts[
            ["product_id", "stock_qty", "reorder_level", "stock_status"]
        ].head(20).to_string(index=False)
    )


# ------------------------------------------------------------
# 8. INVENTORY AGEING
# ------------------------------------------------------------

if "last_grn_date" in inventory.columns:
    inventory["inventory_age_days"] = (
        pd.Timestamp.today().normalize() - inventory["last_grn_date"]
    ).dt.days

    inventory["age_bucket"] = pd.cut(
        inventory["inventory_age_days"],
        bins=[-1, 30, 60, 90, np.inf],
        labels=["0-30 Days", "31-60 Days", "61-90 Days", "90+ Days"],
    )

    ageing = (
        inventory.groupby("age_bucket", observed=False)
        .agg(
            stock_units=("stock_qty", "sum"),
            inventory_value=("inventory_value", "sum"),
        )
        .reset_index()
    )

    ageing.to_csv(OUTPUT_DIR / "inventory_ageing.csv", index=False)

    print("\nINVENTORY AGEING")
    print(ageing.to_string(index=False))


# ------------------------------------------------------------
# 9. EXPIRING INVENTORY - NEXT 30 DAYS
# ------------------------------------------------------------

if "expiry_date" in inventory.columns:
    today = pd.Timestamp.today().normalize()
    expiring = inventory[
        inventory["expiry_date"].between(
            today, today + pd.Timedelta(days=30), inclusive="both"
        )
    ].copy()

    expiring["days_to_expiry"] = (
        expiring["expiry_date"] - today
    ).dt.days

    expiring.to_csv(OUTPUT_DIR / "expiring_inventory.csv", index=False)

    print("\nEXPIRING INVENTORY")
    print(expiring.head(10).to_string(index=False))


# ------------------------------------------------------------
# 10. GRN REJECTION RATE
# ------------------------------------------------------------

if {"received_qty", "rejected_qty"}.issubset(grns.columns):
    received = grns["received_qty"].sum()
    rejected = grns["rejected_qty"].sum()
    rejection_rate = (rejected / received * 100) if received else 0

    grn_kpi = pd.DataFrame(
        [{
            "received_units": received,
            "rejected_units": rejected,
            "rejection_rate_pct": round(rejection_rate, 2),
        }]
    )

    grn_kpi.to_csv(OUTPUT_DIR / "grn_quality_summary.csv", index=False)

    print("\nGRN QUALITY")
    print(grn_kpi.to_string(index=False))


# ------------------------------------------------------------
# 11. ORDER FULFILLMENT AND ON-TIME DELIVERY
# ------------------------------------------------------------

if "order_status" in orders.columns:
    delivered = orders["order_status"].astype(str).str.lower().eq("delivered")
    fulfillment_rate = delivered.mean() * 100 if len(orders) else 0
else:
    delivered = pd.Series(False, index=orders.index)
    fulfillment_rate = 0

order_kpi = pd.DataFrame(
    [{
        "total_orders": len(orders),
        "delivered_orders": int(delivered.sum()),
        "fulfillment_rate_pct": round(fulfillment_rate, 2),
    }]
)

if {"promised_date", "delivered_date"}.issubset(orders.columns):
    delivered_orders = orders[orders["delivered_date"].notna()].copy()
    if len(delivered_orders):
        on_time = delivered_orders["delivered_date"] <= delivered_orders["promised_date"]
        order_kpi["on_time_delivery_pct"] = round(on_time.mean() * 100, 2)
        order_kpi["avg_delivery_days"] = round(
            (delivered_orders["delivered_date"] - delivered_orders["order_date"])
            .dt.days.mean(),
            2,
        )

order_kpi.to_csv(OUTPUT_DIR / "order_fulfillment_summary.csv", index=False)

print("\nORDER FULFILLMENT")
print(order_kpi.to_string(index=False))


# ------------------------------------------------------------
# 12. EXECUTIVE SUMMARY
# ------------------------------------------------------------

executive_summary = pd.DataFrame(
    [{
        "total_products": products["product_id"].nunique()
        if "product_id" in products.columns else len(products),
        "total_warehouses": data["warehouses"]["warehouse_id"].nunique()
        if "warehouse_id" in data["warehouses"].columns else len(data["warehouses"]),
        "stock_units": total_stock,
        "inventory_value": round(total_inventory_value, 2),
        "units_sold": sales["quantity"].sum(),
        "net_sales": round(sales["net_sales"].sum(), 2),
        "fulfillment_rate_pct": round(fulfillment_rate, 2),
    }]
)

executive_summary.to_csv(
    OUTPUT_DIR / "executive_summary.csv", index=False
)

print("\nEXECUTIVE SUMMARY")
print(executive_summary.to_string(index=False))

print("\n" + "=" * 70)
print(f"Analysis completed. Output files saved to: {OUTPUT_DIR}")
print("=" * 70)
