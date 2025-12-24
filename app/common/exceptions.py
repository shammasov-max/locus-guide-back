from fastapi import HTTPException, status


class AuthException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class InvalidCredentialsException(AuthException):
    def __init__(self):
        super().__init__(detail="Invalid email or password")


class InvalidTokenException(AuthException):
    def __init__(self):
        super().__init__(detail="Invalid or expired token")


class UserExistsException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )


class UserNotFoundException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


class GoogleAuthException(HTTPException):
    def __init__(self, detail: str = "Google authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
