from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from db.database import db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    from api.config_api import load_saved_config
    await load_saved_config()
    from api.qq_api import load_qq_config
    await load_qq_config()
    yield
    await db.close()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
