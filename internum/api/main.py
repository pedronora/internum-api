import logging
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from internum.api.schemas import ErrorResponse, Status
from internum.core.database import get_session
from internum.modules.auth.routers import router as auth_router
from internum.modules.home.routers import router as home_router
from internum.modules.legal_briefs.routers import router as legal_brief_router
from internum.modules.library.routers import router as library_router
from internum.modules.notices.routers import router as notices_router
from internum.modules.users.routers import router as users_router
from internum.modules.vacation.routers import router as vacation_router

Session = Annotated[AsyncSession, Depends(get_session)]
logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1')
router.include_router(auth_router)
router.include_router(home_router)
router.include_router(legal_brief_router)
router.include_router(library_router)
router.include_router(notices_router)
router.include_router(users_router)
router.include_router(vacation_router)


@router.get(
    '/status',
    response_model=Status,
    responses={
        HTTPStatus.SERVICE_UNAVAILABLE: {'model': ErrorResponse},
    },
    tags=['API'],
)
async def status_db(session: Session):
    try:
        await session.execute(select(1))
    except SQLAlchemyError:
        logger.exception('Falha ao verificar a conexão com o banco de dados.')
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail='Serviço indisponível',
        )

    return {'status': 'ok'}
