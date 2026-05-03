# main.py — app init, lifespan, router mount, uvicorn run

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from api import all_routers


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure()
    yield


app = FastAPI(title="minimal", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

for router in all_routers:
    app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=4096, reload=False)
