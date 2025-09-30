def user_public(u):
    return {"id": str(u.id), "username": u.username, "email": u.email, "role": u.role}
