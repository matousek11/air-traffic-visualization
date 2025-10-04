"""
Handle request on users coming through web browser
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

views = Jinja2Templates(directory="views")

@app.get("/", response_class=HTMLResponse)
def display_mtcd(request: Request) -> HTMLResponse:
    """
    Display map with position of planes and its routes
    """
    return views.TemplateResponse("index.html", {"request": request})
