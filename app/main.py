from fastapi import FastAPI
from app.core.config import lifespan
from app.api.routes import router

# Initialize FastAPI with the AWS startup lifespan
app = FastAPI(lifespan=lifespan)

# Hook up the web routes
app.include_router(router)

@app.get("/health")
def health_check():
    return {"status": "healthy, fully refactored, and ready for Phase 3!"}