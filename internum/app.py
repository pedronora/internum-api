from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from internum.api.main import router as main_router
from internum.core.scheduler.scheduler import scheduler, start_scheduler
from internum.core.settings import Settings

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title='Internum API - 1 RI Cascavel', lifespan=lifespan)


origins = [
    settings.FRONTEND_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(main_router)
