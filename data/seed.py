"""data/seed.py — populates warehouse/shelfpulse.duckdb with synthetic CPG data.

Generates ~50k weekly_sales rows + ~25k inventory_snapshots rows across
40 products, 12 regions, 4 channels, 104 weeks. Three planted anomalies
make the demo questions deterministic:

  1. Atlas Cola & Quench Sparkling underperform in Northeast Q1 2026 (-12%)
  2. Snack category gets a +18% promo lift Jan-Feb 2026, then -6% drag in March
  3. NorthBolt 500ml weeks_of_cover declines linearly toward 1.8 by W22 2026
"""

import random
from datetime import datetime, timedelta

import duckdb

DB_PATH = "warehouse/shelfpulse.duckdb"
SEED = 42

# Category -> allowed subcategories (mirrors Subcategory Literal in mcp_server/models.py)
SUBCATEGORY_BY_CATEGORY: dict[str, list[str]] = {
    "beverage": ["cola", "sparkling", "juice", "water"],
    "energy":   ["energy_drink"],
    "snack":    ["chips", "bars", "pretzels", "cookies"],
}

PREFIX_BY_CATEGORY: dict[str, str] = {
    "beverage": "BEV",
    "energy":   "ENG",
    "snack":    "SNK",
}


def seed_database() -> None:
    print("Connecting to DuckDB warehouse...")
    conn = duckdb.connect(DB_PATH)

    # Wipe in FK-safe order
    conn.execute("DELETE FROM inventory_snapshots;")
    conn.execute("DELETE FROM weekly_sales;")
    conn.execute("DELETE FROM channels;")
    conn.execute("DELETE FROM regions;")
    conn.execute("DELETE FROM products;")

    # ------------------------------------------------------------------
    # 1. Dimensions
    # ------------------------------------------------------------------
    channels = [
        ("GRO", "Grocery"),
        ("CST", "Convenience"),
        ("CLU", "Club"),
        ("ONL", "Online"),
    ]
    conn.executemany("INSERT INTO channels VALUES (?, ?);", channels)

    # 9 US Census divisions + 3 international segments
    regions = [
        ("NE",  "Northeast"),
        ("MA",  "Mid-Atlantic"),
        ("ENC", "East North Central"),
        ("WNC", "West North Central"),
        ("SA",  "South Atlantic"),
        ("ESC", "East South Central"),
        ("WSC", "West South Central"),
        ("MTN", "Mountain"),
        ("PAC", "Pacific"),
        ("CAN", "Canada"),
        ("MEX", "Mexico"),
        ("EUR", "Europe"),
    ]
    conn.executemany("INSERT INTO regions VALUES (?, ?);", regions)

    # ------------------------------------------------------------------
    # Products: 10 hand-curated + 30 generated. All within enum bounds.
    # ------------------------------------------------------------------
    products: list[tuple] = [
        # Beverages
        ("SKU-BEV-001", "Atlas Cola",       "beverage", "cola",      "12oz x 12", 5.99, 2.10),
        ("SKU-BEV-002", "Quench Sparkling", "beverage", "sparkling", "500ml x 6", 4.49, 1.80),
        ("SKU-BEV-003", "Citrus Splash",    "beverage", "juice",     "64oz",      3.99, 1.50),
        ("SKU-BEV-004", "Pure H2O",         "beverage", "water",     "24 pack",   6.99, 1.20),
        # Energy
        ("SKU-ENG-001", "NorthBolt 500ml",  "energy",   "energy_drink", "500ml",    2.99, 0.95),
        ("SKU-ENG-002", "Volt Surge",       "energy",   "energy_drink", "16oz",     3.49, 1.10),
        ("SKU-ENG-003", "Apex Raw",         "energy",   "energy_drink", "12oz x 4", 8.99, 3.20),
        # Snacks
        ("SKU-SNK-001", "NorthSnack Chips", "snack",    "chips",     "10oz",      3.29, 0.90),
        ("SKU-SNK-002", "ChocoBars",        "snack",    "bars",      "6 count",   4.99, 1.75),
        ("SKU-SNK-003", "Pretzel Twists",   "snack",    "pretzels",  "16oz",      2.79, 0.80),
    ]

    random.seed(SEED)
    brands = ["Apex", "Sierra", "Summit", "Glow", "Crisp", "Harbor", "Northwind"]
    pack_options = {
        "beverage": ["8oz", "12oz x 6", "1 Liter", "500ml x 6"],
        "energy":   ["8.4oz", "16oz", "500ml", "12oz x 4"],
        "snack":    ["6oz", "10oz", "16oz", "Single Bag"],
    }

    # Per-category counters so SKU prefix stays consistent with category
    counters = {"BEV": 5, "ENG": 4, "SNK": 4}  # next available number per prefix

    while len(products) < 40:
        cat = random.choice(["beverage", "energy", "snack"])
        sub = random.choice(SUBCATEGORY_BY_CATEGORY[cat])
        prefix = PREFIX_BY_CATEGORY[cat]
        num = counters[prefix]
        counters[prefix] += 1
        sku = f"SKU-{prefix}-{num:03d}"
        brand = f"{random.choice(brands)} {sub.title().replace('_', ' ')}"
        pack = random.choice(pack_options[cat])
        price = round(random.uniform(2.50, 9.90), 2)
        cogs = round(price * random.uniform(0.30, 0.50), 2)
        products.append((sku, brand, cat, sub, pack, price, cogs))

    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?);", products)
    print(f"Seeded dimensions: {len(channels)} channels, {len(regions)} regions, {len(products)} products.")

    # ------------------------------------------------------------------
    # 2. Time horizon: 104 weeks back from May 18, 2026
    # ------------------------------------------------------------------
    end_date = datetime(2026, 5, 18)
    weeks = [end_date - timedelta(weeks=i) for i in range(104)]
    weeks.reverse()  # weeks[0] = oldest, weeks[103] = newest

    sales_rows: list[tuple] = []
    inventory_rows: list[tuple] = []

    print("Generating ~50k fact rows with embedded market trends...")

    # Channel sampling probabilities -> 55/22/14/9 distribution overall
    channel_p = {"GRO": 0.55, "CST": 0.22, "CLU": 0.14, "ONL": 0.09}

    for week_idx, w_date in enumerate(weeks):
        is_q1_2026             = (w_date.year == 2026 and 1 <= w_date.month <= 3)
        is_promo_window        = (w_date.year == 2026 and w_date.month in (1, 2))
        is_post_promo_window   = (w_date.year == 2026 and w_date.month == 3)

        for prod in products:
            p_id, _brand, cat, _sub, _pack, list_price, _cogs = prod

            for reg_id, _reg_name in regions:
                # ---- weekly_sales rows (one per channel that wins its die roll) ----
                for chan_id, _chan_name in channels:
                    if random.random() > channel_p[chan_id]:
                        continue

                    base_units = random.randint(100, 300)

                    # Summer seasonality for liquids
                    if cat in ("beverage", "energy") and w_date.month in (6, 7, 8):
                        base_units = int(base_units * 1.25)

                    promo_flag = False
                    discount_pct = 0.0

                    # Anomaly 1: -12% in NE Q1 2026 for two beverage SKUs
                    if p_id in ("SKU-BEV-001", "SKU-BEV-002") and reg_id == "NE" and is_q1_2026:
                        base_units = int(base_units * 0.88)

                    # Anomaly 2: snack promo lift then cannibalization
                    if cat == "snack":
                        if is_promo_window:
                            promo_flag = True
                            discount_pct = 0.15
                            base_units = int(base_units * 1.18)
                        elif is_post_promo_window:
                            base_units = int(base_units * 0.94)

                    # "gross_sales" here = revenue after discount (i.e. net sales)
                    gross_sales = round(base_units * float(list_price) * (1.0 - discount_pct), 2)

                    sales_rows.append((
                        w_date.date(), p_id, reg_id, chan_id,
                        base_units, gross_sales, promo_flag, round(discount_pct * 100, 2),
                    ))

                # ---- inventory_snapshots: bi-weekly, one row per (week, product, region) ----
                if p_id == "SKU-ENG-001" and week_idx >= 84:
                    # Anomaly 3: linear collapse from 4.5 to 1.8 across weeks 84..103
                    progress = (week_idx - 84) / 19  # /19 so progress=1.0 at week 103
                    weeks_of_cover = round(max(4.5 - progress * 2.7, 1.8), 2)
                    on_hand_units = int(weeks_of_cover * random.randint(40, 60))
                else:
                    weeks_of_cover = round(random.uniform(2.5, 6.0), 2)
                    on_hand_units = random.randint(100, 400)

                if week_idx % 2 == 0:
                    inventory_rows.append((
                        w_date.date(), p_id, reg_id, on_hand_units, weeks_of_cover,
                    ))

    conn.executemany(
        "INSERT INTO weekly_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
        sales_rows,
    )
    conn.executemany(
        "INSERT INTO inventory_snapshots VALUES (?, ?, ?, ?, ?);",
        inventory_rows,
    )

    sales_row = conn.execute("SELECT COUNT(*) FROM weekly_sales;").fetchone()
    inv_row = conn.execute("SELECT COUNT(*) FROM inventory_snapshots;").fetchone()
    assert sales_row is not None and inv_row is not None  # COUNT(*) always returns one row
    total_sales = sales_row[0]
    total_inv = inv_row[0]
    conn.close()

    print("\nWarehouse population complete.")
    print(f"  weekly_sales rows:        {total_sales:,}")
    print(f"  inventory_snapshots rows: {total_inv:,}")


if __name__ == "__main__":
    seed_database()