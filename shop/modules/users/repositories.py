from .models import User, Address
from typing import Optional
from .mappers import user_public, address_public
from bson import ObjectId


def get_by_email(email: str):
    return User.objects(email=email).first()


def get_by_username(username: str):
    return User.objects(username=username).first()


def email_exists(email: str) -> bool:
    return User.objects(email=email).first() is not None


def username_exists(username: str) -> bool:
    return User.objects(username=username).first() is not None


def create_user(username: str, email: str, password_hash: str, role: str = "user"):
    return User(username=username, email=email, password_hash=password_hash, role=role).save()

def _get_user(uid: str) -> Optional[User]:
    try: oid = ObjectId(uid)
    except Exception: return None
    return User.objects(id=oid).first()

def _find_addr(u: User, addr_id: str) -> Optional[Address]:
    return next((a for a in u.addresses if a.id == addr_id), None)

def _ensure_single_default(u:User, target: Address | None = None):
    if target is None:
        return
    for a in u.addresses:
        a.is_default = (a is target)


def get_public_by_id(uid: str) -> Optional[dict]:
    u = _get_user(uid)
    return user_public(u) if u else None

def update_user(uid: str, first_name: str | None, last_name: str | None, phone:str | None, avatar: str | None) -> Optional[dict]:
    u = _get_user(uid)
    if not u: return None
    if first_name is not None: u.first_name = first_name
    if last_name is not None: u.last_name = last_name
    if phone is not None: u.phone = phone
    if avatar is not None: u.avatar = avatar
    u.save()
    return user_public(u)


def list_addresses(uid: str) -> Optional[list[dict]]:
    u = _get_user(uid)
    if not u: return None
    return [address_public(a) for a in u.addresses]

def add_address(uid: str, address_line: str, city: str, is_default: bool = False) -> Optional[dict]:
    u = _get_user(uid)
    if not u: return None
    addr = Address(address_line=address_line, city=city, is_default=is_default)
    if is_default:
        _ensure_single_default(u, addr)
    u.addresses.append(addr)
    u.save()
    return address_public(addr)

def update_address(uid: str, addr_id: str, address_line: str, city: str, is_default: bool = False) -> Optional[bool]:
    u = _get_user(uid)
    if not u: return None
    target = _find_addr(u, addr_id)
    if not target: return None
    if address_line is not None: target.address_line = address_line
    if city is not None: target.city = city
    if is_default:
        _ensure_single_default(u, target)
    u.save()
    return True

def delete_address(uid: str, addr_id: str) -> Optional[bool]:
    u = _get_user(uid)
    if not u: return None
    before = len(u.addresses)
    u.addresses = [a for a in u.addresses if a.id != addr_id]
    if len(u.addresses) == before: return False
    u.save()
    return True

def set_default(uid:str, addr_id:str) -> Optional[bool]:
    u = _get_user(uid)
    if not u: return None
    target = _find_addr(u, addr_id)
    if not target: return None
    _ensure_single_default(u, target)
    u.save()
    return True

