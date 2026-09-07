from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api import router
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="orby4middleware", version="0.2.0", lifespan=lifespan)
app.include_router(router)
