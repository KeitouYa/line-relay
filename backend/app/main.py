import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, relay, quotes, admin

app = FastAPI(
    title="Line Relay API",
    description="AI-powered movie quote relay video generator",
    version="0.1.0",
)

origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(relay.router, prefix="/api/relay", tags=["relay"])
app.include_router(quotes.router, prefix="/api/quotes", tags=["quotes"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
