from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import stacks, assignments, canvas

app = FastAPI(title="TaskStack API", version="1.4.0")
init_db()

app.include_router(stacks.router)
app.include_router(assignments.router)
app.include_router(canvas.router)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- UI Root ---

@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")
