from fastapi import FastAPI

app = FastAPI(title="Mistake Note AI Assistant")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
