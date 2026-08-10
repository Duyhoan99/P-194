"""Authentication REST endpoints adhering strictly to API_CONTRACT.md section 4.2."""

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from src.clinical.canonical import UserMe
from src.clinical.demo_auth import (
    DEMO_SESSION_COOKIE,
    authenticate_demo_credentials,
    create_demo_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class DemoLoginRequest(BaseModel):
    username: str
    password: str


DEFAULT_CLINICIAN = UserMe(
    user_id="usr_doctor_demo",
    display_name="BS. Nguyễn Văn A",
    tenant_id="ten_demo",
    roles=["clinician"],
    permissions=[
        "patient.list",
        "patient.process",
        "clinical.read",
        "clinical.import",
        "clinical.verify",
        "review.generate",
        "review.read",
        "review.edit",
        "review.approve",
        "review.export",
        "ask.create",
        "evidence.read",
        "feedback.create",
        "memory.read",
    ],
)


@router.post("/login", response_model=UserMe)
def login(payload: LoginRequest, response: Response) -> UserMe:
    """Authenticates doctor email/password, sets HttpOnly session cookie, and returns UserMe."""
    if not payload.email or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID", "message": "Email hoặc mật khẩu không đúng."},
        )

    session, max_age = create_demo_session("doctor-1")
    response.set_cookie(
        key=DEMO_SESSION_COOKIE,
        value=session,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return DEFAULT_CLINICIAN



@router.post("/demo-login", status_code=status.HTTP_204_NO_CONTENT)
def demo_login(payload: DemoLoginRequest, response: Response) -> Response:
    """Legacy demo login endpoint setting session cookie."""
    try:
        username = authenticate_demo_credentials(payload.username, payload.password)
        session, max_age = create_demo_session(username)
    except Exception:
        raise HTTPException(status_code=503, detail="Demo authentication is unavailable.")
    
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.set_cookie(
        key=DEMO_SESSION_COOKIE,
        value=session,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return resp


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    """Clear session cookie."""
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(DEMO_SESSION_COOKIE, httponly=True, samesite="lax", path="/")
    return resp


@router.get("/me", response_model=UserMe)
def get_me() -> UserMe:
    """Returns authenticated user profile."""
    return DEFAULT_CLINICIAN
