from typing import Literal, Optional

from pydantic import BaseModel, Field


MetricName = Literal[
    "units_sold",
    "gross_sales",
    "cost_of_goods_sold",
    "gross_profit",
    "gross_margin_pct",
    "avg_discount_pct"
]

ToolName = Literal[
    "list_products",
    "list_regions",
    "list_channels",
    "query_sales",
    "compute_kpi",
    "compare_periods",
    "detect_stockout_risk"
]

Subcategory = Literal[
    "cola",
    "sparkling",
    "juice",
    "water",
    "energy_drink",
    "chips",    
    "bars",
    "pretzels",
    "cookies"
]


class Product(BaseModel):
    product_id: str = Field(..., description="Unique SKU identifier, e.g. SKU-BEV-001")
    brand:str
    category:str
    subcategory:str
    pack_size:str
    list_price:float
    cogs:float


class Region(BaseModel):
    region_id: str = Field(..., description="Two letter region identifier, e.g. NE")
    region_name: str

    
class Channel(BaseModel):
    channel_id: str = Field(..., description="Three letter channel identifier, e.g. GRO")
    channel_name: str


class SalesQueryFilter(BaseModel):
    product_id: Optional[str] = None
    category: Optional[str] = None
    region_id: Optional[str] = None
    channel_id: Optional[str] = None
    start_date: Optional[str] = Field(None, description="ISO date string YYYY-MM-DD format")
    end_date: Optional[str] = Field(None, description="ISO date string YYYY-MM-DD format")


class KPISnapshot(BaseModel):
    units_sold: int
    gross_sales: float
    cost_of_goods_sold: float
    gross_profit: float
    gross_margin_pct: float
    promo_sales_share_pct: float


class PeriodComparison(BaseModel):
    metric: str
    period_a: str
    period_b: str
    value_a: float
    value_b: float
    absolute_change: float
    percentage_change: float


class StockoutRisk(BaseModel):
    prdouct_id: str
    region_id: str
    on_hands_unit: int
    weeks_of_cover: float
    risk_level:str = Field(..., description="CRITICAL (<= 2.0 weeks), WARNING (<= 3.5 weeks), or OK")
