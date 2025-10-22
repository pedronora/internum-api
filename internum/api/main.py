from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from internum.api.schemas import ErrorResponse, Status
from internum.core.database import get_session
from internum.modules.auth.routers import router as auth_router
from internum.modules.legal_briefs.routers import router as legal_brief_router
from internum.modules.notices.routers import router as notices_router
from internum.modules.users.routers import router as users_router

Session = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter(prefix='/api/v1')
router.include_router(auth_router)
router.include_router(legal_brief_router)
router.include_router(notices_router)
router.include_router(users_router)


@router.get(
    '/status',
    response_model=Status,
    responses={
        HTTPStatus.NOT_FOUND: {'model': ErrorResponse},
        HTTPStatus.INTERNAL_SERVER_ERROR: {'model': ErrorResponse},
    },
    tags=['API'],
)
async def status_db(session: Session):
    try:
        result = await session.execute(
            select(func.version(), func.current_database(), func.now())
        )
        status = result.fetchone()

        if status:
            version, current_db, current_time = status
            return {
                'status': 'ok',
                'version_db': version,
                'current_db': current_db,
                'current_time': current_time,
            }
        else:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail='No data found'
            )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f'Database error: {str(e)}',
        )
