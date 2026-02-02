"""Mock product database"""

from typing import Optional
from ..models.product import Product, ProductCategory

# Mock product catalog
PRODUCTS: dict[str, Product] = {
    "prod-001": Product(
        id="prod-001",
        name="Sony WH-1000XM5 Wireless Headphones",
        description="Industry-leading noise cancellation with 30-hour battery life. Premium sound quality with LDAC support.",
        price=349.99,
        category=ProductCategory.ELECTRONICS,
        sku="SONY-WH1000XM5-BLK",
        image_url="/static/images/sony-headphones.jpg",
        stock_quantity=50,
    ),
    "prod-002": Product(
        id="prod-002",
        name="Apple AirPods Pro (2nd Gen)",
        description="Active Noise Cancellation, Adaptive Transparency, and Personalized Spatial Audio with dynamic head tracking.",
        price=249.00,
        category=ProductCategory.ELECTRONICS,
        sku="APPLE-APP2-WHT",
        image_url="/static/images/airpods-pro.jpg",
        stock_quantity=100,
    ),
    "prod-003": Product(
        id="prod-003",
        name="Samsung Galaxy Tab S9",
        description="11-inch Dynamic AMOLED 2X display. Snapdragon 8 Gen 2. S Pen included.",
        price=799.99,
        category=ProductCategory.ELECTRONICS,
        sku="SAMSUNG-TABS9-GRY",
        image_url="/static/images/galaxy-tab.jpg",
        stock_quantity=30,
    ),
    "prod-004": Product(
        id="prod-004",
        name="Patagonia Better Sweater Jacket",
        description="Classic fleece jacket made with recycled polyester. Perfect for layering.",
        price=139.00,
        category=ProductCategory.CLOTHING,
        sku="PATA-BSJKT-NVY-M",
        image_url="/static/images/patagonia-sweater.jpg",
        stock_quantity=75,
    ),
    "prod-005": Product(
        id="prod-005",
        name="Nike Air Max 90",
        description="Iconic design with Max Air cushioning. Leather and textile upper.",
        price=130.00,
        category=ProductCategory.CLOTHING,
        sku="NIKE-AM90-WHT-10",
        image_url="/static/images/airmax90.jpg",
        stock_quantity=60,
    ),
    "prod-006": Product(
        id="prod-006",
        name="Dyson V15 Detect Vacuum",
        description="Laser reveals microscopic dust. Piezo sensor counts and sizes particles.",
        price=749.99,
        category=ProductCategory.HOME,
        sku="DYSON-V15DET-GLD",
        image_url="/static/images/dyson-v15.jpg",
        stock_quantity=25,
    ),
    "prod-007": Product(
        id="prod-007",
        name="KitchenAid Stand Mixer",
        description="5.5-Quart bowl-lift stand mixer. 11 speeds. Includes flat beater, dough hook, and wire whip.",
        price=449.99,
        category=ProductCategory.HOME,
        sku="KA-MIXER-RED-55",
        image_url="/static/images/kitchenaid.jpg",
        stock_quantity=40,
    ),
    "prod-008": Product(
        id="prod-008",
        name="Yeti Tundra 45 Cooler",
        description="Rotomolded construction. PermaFrost insulation. Bear-resistant certified.",
        price=325.00,
        category=ProductCategory.SPORTS,
        sku="YETI-T45-WHT",
        image_url="/static/images/yeti-cooler.jpg",
        stock_quantity=35,
    ),
    "prod-009": Product(
        id="prod-009",
        name="Garmin Forerunner 965",
        description="Premium GPS running watch with AMOLED display. Advanced training metrics and maps.",
        price=599.99,
        category=ProductCategory.SPORTS,
        sku="GARM-FR965-BLK",
        image_url="/static/images/garmin-watch.jpg",
        stock_quantity=20,
    ),
    "prod-010": Product(
        id="prod-010",
        name="Atomic Habits by James Clear",
        description="An Easy & Proven Way to Build Good Habits & Break Bad Ones. Hardcover.",
        price=24.99,
        category=ProductCategory.BOOKS,
        sku="BOOK-ATOMIC-HC",
        image_url="/static/images/atomic-habits.jpg",
        stock_quantity=200,
    ),
}


class ProductDatabase:
    """In-memory product database for mock merchant"""

    def __init__(self):
        self.products = PRODUCTS.copy()

    def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID"""
        return self.products.get(product_id)

    def search_products(
        self,
        query: Optional[str] = None,
        category: Optional[ProductCategory] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Product], int]:
        """
        Search products with filters.

        Returns:
            Tuple of (matching products, total count)
        """
        results = list(self.products.values())

        # Filter by search query
        if query:
            query_lower = query.lower()
            results = [
                p for p in results
                if query_lower in p.name.lower() or query_lower in p.description.lower()
            ]

        # Filter by category
        if category:
            results = [p for p in results if p.category == category]

        # Filter by price range
        if min_price is not None:
            results = [p for p in results if p.price >= min_price]
        if max_price is not None:
            results = [p for p in results if p.price <= max_price]

        # Filter by stock
        if in_stock_only:
            results = [p for p in results if p.in_stock and p.stock_quantity > 0]

        # Get total before pagination
        total = len(results)

        # Apply pagination
        results = results[offset : offset + limit]

        return results, total

    def get_all_products(self) -> list[Product]:
        """Get all products"""
        return list(self.products.values())

    def update_stock(self, product_id: str, quantity_change: int) -> bool:
        """
        Update product stock.

        Args:
            product_id: Product to update
            quantity_change: Positive to add, negative to remove

        Returns:
            True if successful
        """
        product = self.products.get(product_id)
        if not product:
            return False

        new_quantity = product.stock_quantity + quantity_change
        if new_quantity < 0:
            return False

        product.stock_quantity = new_quantity
        product.in_stock = new_quantity > 0
        return True


# Singleton instance
product_db = ProductDatabase()
