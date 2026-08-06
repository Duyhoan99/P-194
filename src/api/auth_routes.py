"""Development/test-only demo session endpoints."""

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, Response, status
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

from src.clinical.demo_auth import (
    DEMO_SESSION_COOKIE,
    authenticate_demo_credentials,
    create_demo_session,
)
from src.clinical.errors import ClinicalAuthNotConfigured

router = APIRouter(prefix="/auth", tags=["auth"])


class DemoLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/demo-login", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def demo_login(payload: DemoLoginRequest) -> Response:
    """Set a signed cookie for a fixed development/test demo account."""
    try:
        username = authenticate_demo_credentials(payload.username, payload.password)
        session, max_age = create_demo_session(username)
    except ClinicalAuthNotConfigured as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo authentication is unavailable.") from error
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.set_cookie(
        key=DEMO_SESSION_COOKIE,
        value=session,
        max_age=max_age,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def logout() -> Response:
    """Clear the development/test session cookie."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(DEMO_SESSION_COOKIE, httponly=True, samesite="strict", path="/")
    return response
