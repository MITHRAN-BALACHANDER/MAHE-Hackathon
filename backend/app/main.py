from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import api

app = FastAPI(
    title="SignalRoute AI API",
    description="Smart route intelligence for balancing ETA and cellular connectivity.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to SignalRoute AI Backend", "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

app.include_router(api.router, prefix="/api")
