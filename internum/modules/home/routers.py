from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends

from internum.core.permissions import CurrentUser
from internum.modules.home.schemas import HomeSummary
from internum.modules.home.services import HomeService

router = APIRouter(prefix='/home', tags=['Home'])


@router.get('/', status_code=HTTPStatus.OK, response_model=HomeSummary)
async def get_home_data(
    current_user: CurrentUser,
    home_service: Annotated[HomeService, Depends(HomeService)],
):
    return await home_service.get_summary_data(
        current_user.id, current_user.created_at
    )
