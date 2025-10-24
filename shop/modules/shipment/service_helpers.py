
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ...core.exceptions import AppError
from ..users.models import Address, User
from ...core.utils import normalize_required_string


@dataclass
class ResolvedAddress:
    address_line: str
    city: str
    source: str
    user_address_id: Optional[str] = None


def _normalize_optional_string(
    value: Any, *, field: str, code: str, max_length: int
) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AppError(f"{field} must be a string", 400, name=code)
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        raise AppError(f"{field} is too long", 400, name=code)
    return cleaned


def _get_user_address(user: Optional[User], address_id: Any) -> Address:
    if not user:
        raise AppError(
            "address_id can only be used with authenticated users",
            400,
            name="INVALID_ADDRESS",
        )
    if address_id is None:
        raise AppError("address_id is required", 400, name="INVALID_ADDRESS")
    if not isinstance(address_id, str):
        raise AppError("address_id must be a string", 400, name="INVALID_ADDRESS")
    cleaned = address_id.strip()
    if not cleaned:
        raise AppError("address_id is required", 400, name="INVALID_ADDRESS")
    for address in user.addresses or []:
        if getattr(address, "id", None) == cleaned:
            return address
    raise AppError("Address not found", 404, name="ADDRESS_NOT_FOUND")


def _parse_address_payload(address_payload: Any) -> tuple[str, str]:
    if not isinstance(address_payload, dict):
        raise AppError("address must be an object", 400, name="INVALID_ADDRESS")
    address_line = normalize_required_string(
        address_payload.get("address_line"),
        field="Address line",
        code="INVALID_ADDRESS_LINE",
        max_length=255,
    )
    city = normalize_required_string(
        address_payload.get("city"),
        field="City",
        code="INVALID_CITY",
        max_length=120,
    )
    return address_line, city

def _build_resolved_user_address(address: Address) -> ResolvedAddress:
    address_line = normalize_required_string(
        getattr(address, "address_line", None),
        field="Address line",
        code="INVALID_ADDRESS_LINE",
        max_length=255,
    )
    city = normalize_required_string(
        getattr(address, "city", None),
        field="City",
        code="INVALID_CITY",
        max_length=120,
    )
    return ResolvedAddress(
        address_line=address_line,
        city=city,
        source="user",
        user_address_id=getattr(address, "id", None),
    )

def _resolve_address(
    user: Optional[User], address_id: Any, address_payload: Any
) -> ResolvedAddress:
    if address_id not in (None, ""):
        address = _get_user_address(user, address_id)
        return _build_resolved_user_address(address)

    if address_payload is not None:
        address_line, city = _parse_address_payload(address_payload)
        return ResolvedAddress(
            address_line=address_line,
            city=city,
            source="user" if user else "guest",
            user_address_id=None,
        )
    if user:
        default_address = next(
            (address for address in user.addresses or [] if getattr(address, "is_default", False)),
            None,
        )
        if default_address is not None:
            return _build_resolved_user_address(default_address)

    raise AppError(
        "Either address_id or address object must be provided",
        400,
        name="INVALID_ADDRESS",
    )


def _normalize_note(value: Any) -> Optional[str]:
    return _normalize_optional_string(
        value,
        field="Note",
        code="INVALID_NOTE",
        max_length=500,
    )


def _normalize_recipient_name(value: Any) -> Optional[str]:
    return _normalize_optional_string(
        value,
        field="Recipient name",
        code="INVALID_RECIPIENT_NAME",
        max_length=120,
    )


def _normalize_recipient_phone(value: Any) -> Optional[str]:
    return _normalize_optional_string(
        value,
        field="Recipient phone",
        code="INVALID_RECIPIENT_PHONE",
        max_length=30,
    )