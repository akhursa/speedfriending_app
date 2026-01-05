from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()
@app.get("/")
def read_root():
    return HTMLResponse(content="<h1>Welcome to the Speed Friending application!</h1>")
@app.post("/events")