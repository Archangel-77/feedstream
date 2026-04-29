from fastapi import FastAPI

app = FastAPI(
    title="feedstream",
    description="Real-time AIS maritime data ingestion and query service",
    version="0.1.0",
)


@app.get("/healthz", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}
