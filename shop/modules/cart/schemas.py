
from dataclasses import dataclass
from typing import Optional


@dataclass
class CartIdentityDTO:
    user_id: Optional[str]
    session_id: Optional[str]


@dataclass
class AddCartItemDTO:
    product_id: str
    quantity: int = 1


@dataclass
class UpdateCartItemDTO:
    quantity: int


@dataclass
class MergeCartDTO:
    session_id: str