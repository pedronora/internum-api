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


def create_app(docs_enabled: bool | None = None) -> FastAPI:
    if docs_enabled is None:
        docs_enabled = settings.DOCS_ENABLED

    return FastAPI(
        title='Internum API - 1 RI Cascavel',
        lifespan=lifespan,
        docs_url='/docs' if docs_enabled else None,
        redoc_url='/redoc' if docs_enabled else None,
        openapi_url='/openapi.json' if docs_enabled else None,
    )


app = create_app()


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
