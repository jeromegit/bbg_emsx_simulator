from dataclasses import dataclass

@dataclass
class Order:
    is_active: bool
    order_id: int
    uuid: str
    symbol: str
    side: str
    shares: int
    price: float

