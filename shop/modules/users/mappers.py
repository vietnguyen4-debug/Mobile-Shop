from .models import Address, User


def user_public(u: User) -> dict:
    return {
        "id": str(u.id),
        "username": u.username,
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "phone": u.phone,
        "avatar": u.avatar,
        "role": u.role,
    }


def address_public(a: Address) -> dict:
    return {
        "id": str(a.id),
        "address_line": a.address_line,
        "city": a.city,
        "is_default": a.is_default,
    }