from dataclasses import dataclass

@dataclass
class Order:
    order_id: int
    uuid: str
    symbol: str
    side: str
    shares: int
    price: float