from fastapi import FastAPI
from app.database import engine, Base
from app.routers import doctors

Base.metadata.create_all(bind=engine)

app = FastAPI(title="NeoCortex API", version="1.0.0")

app.include_router(doctors.router, prefix="/api/v1")


@app.get("/")
def health_check():
    return {"status": "ok"}
