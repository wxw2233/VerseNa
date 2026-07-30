from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from auth import (
    MIN_ACCESS_TOKEN_LENGTH,
    SESSION_COOKIE_NAME,
    auth_manager,
    persist_access_token,
)
from config import settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    token: str


class TokenUpdateRequest(BaseModel):
    current_token: str
    new_token: str


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


@router.get("/status")
async def auth_status(request: Request, response: Response):
    authenticated = auth_manager.authenticate(
        request.headers.get("authorization", ""),
        request.cookies.get(SESSION_COOKIE_NAME, ""),
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "required": auth_manager.required,
        "authenticated": authenticated,
    }


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    client_id = _client_id(request)
    if not auth_manager.required:
        return {"status": "ok", "required": False}
    if not auth_manager.can_attempt_login(client_id):
        raise HTTPException(
            status_code=429,
            detail="登录尝试过于频繁，请稍后再试",
            headers={"Retry-After": "60"},
        )
    if not auth_manager.validate_access_token(payload.token):
        auth_manager.record_failed_login(client_id)
        raise HTTPException(status_code=401, detail="访问令牌无效")

    auth_manager.clear_failed_logins(client_id)
    session_id = auth_manager.create_session()
    _set_session_cookie(response, session_id)
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok", "required": True}


@router.put("/token")
async def update_access_token(payload: TokenUpdateRequest, response: Response):
    current_token = payload.current_token.strip()
    if not auth_manager.validate_access_token(current_token):
        raise HTTPException(status_code=403, detail="当前访问令牌无效")
    new_token = payload.new_token.strip()
    if len(new_token) < MIN_ACCESS_TOKEN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"新访问令牌至少需要 {MIN_ACCESS_TOKEN_LENGTH} 个字符",
        )
    if auth_manager.validate_access_token(new_token):
        raise HTTPException(status_code=400, detail="新访问令牌不能与当前令牌相同")

    try:
        persist_access_token(new_token, settings.ACCESS_TOKEN_FILE)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="访问令牌保存失败") from exc

    settings.ACCESS_TOKEN = new_token
    auth_manager.configure(new_token)
    session_id = auth_manager.create_session()
    _set_session_cookie(response, session_id)
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}


@router.post("/logout")
async def logout(request: Request, response: Response):
    auth_manager.revoke_session(request.cookies.get(SESSION_COOKIE_NAME, ""))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", samesite="strict")
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
