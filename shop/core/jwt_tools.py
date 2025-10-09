from datetime import timedelta
from flask_jwt_extended import create_access_token, create_refresh_token

def issue_tokens(identity: str, role: str = "user", access=1, refresh=7):
    claims = {"role": role.lower() if role else "user"}

    return (
        create_access_token(
            identity=identity,
            additional_claims=claims,
            expires_delta=timedelta(days=access)
        ),
        create_refresh_token(
            identity=identity,
            additional_claims=claims,
            expires_delta=timedelta(days=refresh)
        ),
    )
