import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.auth import router as auth_router

app = FastAPI(title="Ctrl X API", version="0.1.0")

origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]
if not all(origins) or "*" in origins:
    raise ValueError("CORS_ORIGINS must contain explicit origins")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(auth_router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid request payload"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
