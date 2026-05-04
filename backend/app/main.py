from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.mistakes import router as mistakes_router
from app.api.notes import router as notes_router
from app.api.uploads import router as uploads_router

app = FastAPI(title="Mistake Note AI Assistant")
app.include_router(auth_router)
app.include_router(mistakes_router)
app.include_router(notes_router)
app.include_router(uploads_router)


@app.exception_handler(HTTPException)
def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
