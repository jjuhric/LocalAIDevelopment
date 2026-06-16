from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router as agent_router
import os

app = FastAPI(
    title="Local Agentic Coordination Grid API",
    description="Enterprise peer-to-peer state graph routing chassis running over Uvicorn parameters."
)

# Permit seamless local networking traffic configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include our active modular endpoint routers
app.include_router(agent_router)

# Ensure the static asset path exists before attempting to mount it
static_path = os.path.join(os.path.dirname(__file__), "..", "static")
if not os.path.exists(static_path):
    os.makedirs(static_path)

# Mount the directory to serve static file indices assets
app.mount("/ui", StaticFiles(directory=static_path), name="static")

# Expose a clean default index fallback straight to the primary dashboard view
@app.get("/")
def read_root_ui_dashboard():
    """Serves the interactive orchestration dashboard directly out of container root handles."""
    return FileResponse(os.path.join(static_path, "index.html"))