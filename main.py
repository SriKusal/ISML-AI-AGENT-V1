from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import RequestLoggingMiddleware, api_router
from app.api.deepseek_routes import router as deepseek_router
from app.api.gemini_routes import router as gemini_router
from app.api.llm_routes import router as llm_router
from app.api.resource_routes import router as resource_router
from app.config import settings

app = FastAPI(title=settings.APP_TITLE, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router)
app.include_router(gemini_router)
app.include_router(deepseek_router)
app.include_router(llm_router)
app.include_router(resource_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "ISML AI AGENT is running"}
