from dataclasses import dataclass

@dataclass
class SignupDTO:
    username: str
    email: str
    password: str

class SigninDTO:
    email: str
    password: str