from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from config import settings
from db.database import db
from auth import SESSION_COOKIE_NAME, auth_manager, is_allowed_origin, validate_network_configuration

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_network_configuration(settings.HOST, settings.ACCESS_TOKEN)
    await db.connect()
    from api.config_api import load_saved_config
    await load_saved_config()
    from api.qq_api import load_qq_config, qq_adapter
    await load_qq_config()
    try:
        yield
    finally:
        await qq_adapter.stop()
        await db.close()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_authentication(request: Request, call_next):
    path = request.url.path
    public_api_paths = {"/api/auth/status", "/api/auth/login"}
    protected_path = path.startswith("/api/") or path in {"/docs", "/redoc", "/openapi.json"}
    if (
        request.method == "OPTIONS"
        or not protected_path
        or path in public_api_paths
        or not auth_manager.required
    ):
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    session_id = request.cookies.get(SESSION_COOKIE_NAME, "")
    if authorization:
        if auth_manager.authenticate_bearer(authorization):
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "访问令牌无效"},
            headers={"Cache-Control": "no-store"},
        )
    if auth_manager.validate_session(session_id):
        request_origin = request.headers.get("origin", "") or request.headers.get("referer", "")
        if request.method in {"GET", "HEAD"} or is_allowed_origin(
            request_origin,
            request.headers.get("host", ""),
            settings.ALLOWED_ORIGINS,
        ):
            return await call_next(request)
        return JSONResponse(status_code=403, content={"detail": "请求来源无效"})
    return JSONResponse(
        status_code=401,
        content={"detail": "需要有效的 VerseNa 访问令牌"},
        headers={"Cache-Control": "no-store"},
    )

@app.get("/health")
async def health():
    import os
    import socket
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "host": settings.HOST,
        "port": settings.PORT,
        "pid": os.getpid(),
        "instance_id": f"{socket.gethostname()}:{os.getpid()}:{settings.PORT}",
    }

from api.chat import router as chat_router
from api.config_api import router as config_router
from api.persona_api import router as persona_router

app.include_router(chat_router)
app.include_router(config_router)
app.include_router(persona_router)

from api.theme_api import router as theme_router
app.include_router(theme_router)

from api.plugin_api import router as plugin_router
app.include_router(plugin_router)

from api.upload_api import router as upload_router
app.include_router(upload_router)

from api.qq_api import router as qq_router
app.include_router(qq_router)

from api.session_api import router as session_router
app.include_router(session_router)

from api.persona_editor_api import router as persona_editor_router
app.include_router(persona_editor_router)

from api.theme_editor_api import router as theme_editor_router
app.include_router(theme_editor_router)

from api.theme_delete_api import router as theme_delete_router
app.include_router(theme_delete_router)

from api.theme_asset_api import router as theme_asset_router
app.include_router(theme_asset_router)

from api.theme_package_api import router as theme_package_router
app.include_router(theme_package_router)

from api.themepack_api import router as themepack_router
app.include_router(themepack_router)

from api.log_api import router as log_router
app.include_router(log_router)

from api.tts_api import router as tts_router
app.include_router(tts_router)

from api.skill_api import router as skill_router
app.include_router(skill_router)

from api.auth_api import router as auth_router
app.include_router(auth_router)

from api.update_api import router as update_router
app.include_router(update_router)

from api.diagnostics_api import router as diagnostics_router
app.include_router(diagnostics_router)


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if full_path.startswith(("api/", "ws/")):
        raise HTTPException(status_code=404)

    frontend_dist = settings.FRONTEND_DIST
    index_path = frontend_dist / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="Frontend build not found")

    requested_path = (frontend_dist / full_path).resolve()
    if requested_path.is_relative_to(frontend_dist) and requested_path.is_file():
        return FileResponse(requested_path)
    return FileResponse(index_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
