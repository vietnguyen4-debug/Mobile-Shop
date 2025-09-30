from .models import User


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


class UserRepo:
    pass
