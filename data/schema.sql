--1. Products Table
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    pack_size TEXT NOT NULL,
    list_price DECIMAL(8,2) NOT NULL,
    cogs DECIMAL(8,2) NOT NULL
);

--2. Regions Table
CREATE TABLE regions (
    region_id TEXT PRIMARY KEY,
    region_name TEXT NOT NULL
);

--3. Channels Table
CREATE TABLE channels (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT NOT NULL
);

--4. Weekly Sales Table
CREATE TABLE weekly_sales (
    week_start DATE NOT NULL,
    product_id TEXT NOT NULL,
    region_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    units_sold INTEGER NOT NULL,
    gross_sales DECIMAL(12,2) NOT NULL,
    promo_flag BOOLEAN NOT NULL,
    discount_pct DECIMAL(5,2) NOT NULL,
    PRIMARY KEY (week_start, product_id, region_id, channel_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (region_id) REFERENCES regions(region_id),
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
);

--5. Inventory Snapshot Table
CREATE TABLE inventory_snapshots (
    snapshot_date DATE NOT NULL,
    product_id TEXT NOT NULL,
    region_id TEXT NOT NULL,
    on_hand_units INTEGER NOT NULL,
    weeks_of_cover DECIMAL(5,2) NOT NULL,
    PRIMARY KEY (snapshot_date, product_id, region_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
);

-- Optimization Index for High-Performance Window Functions & Period-over-Period CTEs
CREATE INDEX weekly_sales_idx ON weekly_sales (product_id, region_id, channel_id, week_start);

-- Stockout risk scans the latest snapshot per (product, region)
CREATE INDEX inventory_snapshots_idx ON inventory_snapshots (snapshot_date, product_id, region_id);