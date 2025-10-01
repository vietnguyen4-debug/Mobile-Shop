from dataclasses import dataclass

@dataclass
class SignupDTO:
    username: str
    email: str
    password: str

@dataclass
class SigninDTO:
    email: str
    password: str

@dataclass
class ChangePasswordDTO:
    old_password: str
    new_password: str

@dataclass
class ForgotPasswordDTO:
    email: str

@dataclass
class ResetPasswordDTO:
    token: str
    new_password: str

@dataclass
class VerifyEmailSendDTO:
    email: str

@dataclass
class VerifyEmailApplyDTO:
    token: str