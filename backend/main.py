import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from database import engine
import models

models.Base.metadata.create_all(bind=engine)

from routes.auth_routes import router as auth_router
from routes.photo_routes import router as photo_router
from routes.user_routes import router as user_router
from routes.follow_routes import router as follow_router
from routes.interaction_routes import router as interaction_router
from routes.order_routes import router as order_router

app = FastAPI(title="SpotGrid API", version="1.1.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(photo_router)
app.include_router(user_router)
app.include_router(follow_router)
app.include_router(interaction_router)
app.include_router(order_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
