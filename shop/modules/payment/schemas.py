from dataclasses import dataclass
from typing import Optional


@dataclass
class OfflinePaymentCreateDTO:
    checkout_id: str
    amount: float
    currency: str = "VND"
    note: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class OfflinePaymentCompleteDTO:
    note: Optional[str] = None
    paid_at: Optional[str] = None