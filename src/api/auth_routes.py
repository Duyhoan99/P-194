"""Authentication REST endpoints adhering strictly to API_CONTRACT.md section 4.2."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from src.api.dependencies import get_access_context
from src.clinical.canonical import UserMe
from src.clinical.demo_auth import (
    DEMO_SESSION_COOKIE,
    authenticate_demo_credentials,
    create_demo_session,
)
from src.clinical.operations import operational_store
from src.clinical.schemas import AccessContext

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


def _get_user_me(username: str) -> UserMe:
    try:
        user = operational_store.get_user(username)
    except KeyError:
        return DEFAULT_CLINICIAN

    role_map = {
        "DOCTOR": "clinician",
        "ADMIN": "administrator",
        "DATA_STEWARD": "auditor",
        "COMPLIANCE": "auditor",
    }

    return UserMe(
        user_id=user.user_id,
        display_name=f"User {user.user_id}",
        tenant_id="ten_demo",
        roles=[role_map.get(user.role, "clinician")],
        permissions=DEFAULT_CLINICIAN.permissions,
    )


@router.post("/login", response_model=UserMe)
def login(payload: LoginRequest, response: Response) -> UserMe:
    """Authenticates email/password, sets HttpOnly session cookie, and returns UserMe."""
    if not payload.email or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID", "message": "Email hoặc mật khẩu không đúng."},
        )

    try:
        username = authenticate_demo_credentials(payload.email, payload.password)
        session, max_age = create_demo_session(username)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID", "message": "Email hoặc mật khẩu không đúng."},
        )

    response.set_cookie(
        key=DEMO_SESSION_COOKIE,
        value=session,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return _get_user_me(username)



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
def get_me(context: AccessContext = Depends(get_access_context)) -> UserMe:
    """Returns authenticated user profile."""
    return _get_user_me(context.user_id)
