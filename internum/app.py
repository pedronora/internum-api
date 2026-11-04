import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from internum.api.main import router as main_router
from internum.core.rate_limiting import limiter
from internum.core.scheduler.scheduler import scheduler, start_scheduler
from internum.core.security_headers import SecurityHeadersMiddleware
from internum.core.settings import Settings

settings = Settings()
logger = logging.getLogger(__name__)


def rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    logger.warning(
        'Rate limit excedido em %s para %s',
        request.url.path,
        request.client.host if request.client else 'desconhecido',
    )

    response = JSONResponse(
        {'detail': 'Muitas tentativas. Tente novamente em instantes.'},
        status_code=429,
    )
    return limiter._inject_headers(  # noqa: SLF001
        response, getattr(request.state, 'view_rate_limit', None)
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    scheduler.shutdown()


def create_app(docs_enabled: bool | None = None) -> FastAPI:
    if docs_enabled is None:
        docs_enabled = settings.DOCS_ENABLED

    app = FastAPI(
        title='Internum API - 1 RI Cascavel',
        lifespan=lifespan,
        docs_url='/docs' if docs_enabled else None,
        redoc_url='/redoc' if docs_enabled else None,
        openapi_url='/openapi.json' if docs_enabled else None,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.SECURE_COOKIE)

    return app


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
