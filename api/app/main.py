from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers import emails_router, gmail_router, agent_router


app = FastAPI(title="Email Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(emails_router, prefix="/api")
app.include_router(gmail_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
