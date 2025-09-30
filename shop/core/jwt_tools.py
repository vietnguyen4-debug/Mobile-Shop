from datetime import timedelta
from flask_jwt_extended import create_access_token, create_refresh_token

def issue_tokens(identity: str, access=1, refresh=7):
    return (
        create_access_token(identity=identity, expires_delta=timedelta(days=access)),
        create_refresh_token(identity=identity, expires_delta=timedelta(days=refresh)),
    )
