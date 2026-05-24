from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import routes, steps, uploads, profiles

app = FastAPI(title="Balangay API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router,   prefix="/api/routes",   tags=["routes"])
app.include_router(steps.router,    prefix="/api/routes",   tags=["steps"])
app.include_router(uploads.router,  prefix="/api/upload",   tags=["uploads"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])

@app.get("/api/health")
def health():
    return {"status": "ok"}