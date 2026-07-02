from dataclasses import dataclass, asdict

SCHEMA_VERSION = "1.0"

_REQUIRED = ("source_site", "source_url", "product_id", "name")


@dataclass
class CanonicalRecord:
    source_site: str
    source_url: str
    scraped_at: str
    authorization_ref: str
    product_id: str
    sku: str
    name: str
    brand: str
    description_raw: str
    description_clean: str
    breadcrumbs: list
    division: str
    category_path: str
    images: list
    specs: dict
    prices: list
    list_price: object          # float | None
    cost_price: object          # float | None
    variants: list
    stock: dict
    attachments: list
    related: list
    raw_ref: str
    schema_version: str = SCHEMA_VERSION

    def validate(self):
        missing = [f for f in _REQUIRED if not getattr(self, f)]
        if missing:
            raise ValueError(f"canonical record missing required fields: {missing}")

    def to_dict(self):
        return asdict(self)

    def to_row(self):
        price = self.prices[0] if self.prices else {}
        return {
            "schema_version": self.schema_version,
            "product_id": self.product_id,
            "sku": self.sku,
            "name": self.name,
            "brand": self.brand,
            "division": self.division,
            "category_path": self.category_path,
            "breadcrumb": " > ".join(self.breadcrumbs),
            "best_price": price.get("value", ""),
            "price_band": price.get("band", ""),
            "price_source": price.get("source", ""),
            "list_price": self.list_price if self.list_price is not None else "",
            "cost_price": self.cost_price if self.cost_price is not None else "",
            "total_stock": self.stock.get("total", ""),
            "image_url": self.images[0] if self.images else "",
            "source_url": self.source_url,
            "description_clean": self.description_clean,
        }
