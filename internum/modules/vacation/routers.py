from http import HTTPStatus
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import get_session
from internum.core.permissions import (
    CurrentUser,
    VerifyAdminCoord,
)
from internum.modules.users.enums import Setor
from internum.modules.users.models import User
from internum.modules.vacation.enums import (
    VacationGrantStatus,
    VacationRequestStatus,
)
from internum.modules.vacation.models import VacationGrant, VacationRequest
from internum.modules.vacation.schemas import (
    VacationAccrualPeriodAlert,
    VacationAccrualPeriodRead,
    VacationConfirmFruitionRequest,
    VacationGrantAdminCreate,
    VacationGrantCreate,
    VacationGrantRead,
    VacationPreviewRequest,
    VacationPreviewResponse,
    VacationRequestCreate,
    VacationRequestListItem,
    VacationRequestRead,
    VacationReviewRequest,
    VacationSellDaysRequest,
)
from internum.modules.vacation.services import CLTVacationService

router = APIRouter(prefix='/vacation', tags=['Vacation'])

Session = Annotated[AsyncSession, Depends(get_session)]


def get_vacation_service(session: Session) -> CLTVacationService:
    return CLTVacationService(session)


async def _load_user(session: Session, user_id: int) -> User:
    user = await session.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Usuário não encontrado'
        )
    return user


def _request_read(request: VacationRequest) -> VacationRequestRead:
    data = VacationRequestRead.model_validate(request)
    if request.user:
        data.user_name = request.user.name
    if request.reviewer:
        data.reviewer_name = request.reviewer.name
    return data


def _grant_read(grant: VacationGrant) -> VacationGrantRead:
    data = VacationGrantRead.model_validate(grant)
    if grant.user:
        data.user_name = grant.user.name
    if grant.approved_by:
        data.approved_by_name = grant.approved_by.name
    if grant.confirmed_by:
        data.confirmed_by_name = grant.confirmed_by.name
    return data


async def _load_request_with_relations(
    session: Session, request_id: int
) -> Optional[VacationRequest]:
    result = await session.execute(
        select(VacationRequest)
        .options(
            selectinload(VacationRequest.user),
            selectinload(VacationRequest.reviewer),
            selectinload(VacationRequest.periods),
        )
        .where(VacationRequest.id == request_id)
    )
    return result.scalar_one_or_none()


# --- Accrual periods ---


@router.get('/accrual-periods', response_model=list[VacationAccrualPeriodRead])
async def list_my_accrual_periods(
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    periods = await service.get_accrual_periods(current_user)
    await session.commit()
    return periods


@router.get(
    '/accrual-periods/{user_id}',
    response_model=list[VacationAccrualPeriodRead],
)
async def list_user_accrual_periods(
    user_id: int,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    user = await _load_user(session, user_id)
    periods = await service.get_accrual_periods(user)
    await session.commit()
    return periods


@router.get(
    '/accrual-periods/{user_id}/{period_id}',
    response_model=VacationAccrualPeriodRead,
)
async def get_user_accrual_period(
    user_id: int,
    period_id: int,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    user = await _load_user(session, user_id)
    period = await service.get_accrual_period(user, period_id)
    if not period:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Período aquisitivo não encontrado',
        )
    await session.commit()
    return period


@router.post(
    '/accrual-periods/{user_id}/{period_id}/sell',
    response_model=VacationAccrualPeriodRead,
)
async def sell_vacation_days(  # noqa: PLR0913, PLR0917
    user_id: int,
    period_id: int,
    data: VacationSellDaysRequest,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    """Venda de dias (abono pecuniário) - apenas admin/coord/RH."""
    user = await _load_user(session, user_id)
    period = await service.get_accrual_period(user, period_id)
    if not period:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Período aquisitivo não encontrado',
        )
    try:
        period = await service.sell_days(period, data.days, current_user)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    await session.commit()
    return await service.get_accrual_period(user, period_id)


@router.post(
    '/accrual-periods/{user_id}/{period_id}/grants',
    status_code=HTTPStatus.CREATED,
    response_model=VacationGrantRead,
)
async def create_vacation_grant(  # noqa: PLR0913, PLR0917
    user_id: int,
    period_id: int,
    data: VacationGrantAdminCreate,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    """Cadastra concessão de férias (admin/coord).

    - normal: marcação direta de férias em período concessivo;
    - retroactive / double_payment: regularização de período expirado.
    """
    data = VacationGrantCreate(
        user_id=user_id,
        accrual_period_id=period_id,
        **data.model_dump(),
    )
    try:
        grant = await service.create_grant(data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    await session.commit()
    await session.refresh(grant)
    return grant


# --- Requests ---


@router.post(
    '/requests',
    status_code=HTTPStatus.CREATED,
    response_model=VacationRequestRead,
)
async def create_vacation_request(
    data: VacationRequestCreate,
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    try:
        request = await service.create_request(current_user, data)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    await session.commit()
    request = await _load_request_with_relations(session, request.id)
    return _request_read(request)


@router.get('/requests', response_model=list[VacationRequestListItem])
async def list_vacation_requests(  # noqa: PLR0913, PLR0917
    session: Session,
    current_user: CurrentUser,
    status: Annotated[Optional[VacationRequestStatus], Query()] = None,
    user_id: Annotated[Optional[int], Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    query = select(VacationRequest).options(selectinload(VacationRequest.user))

    if current_user.role not in {'admin', 'coord'}:
        query = query.where(VacationRequest.user_id == current_user.id)
    elif user_id:
        query = query.where(VacationRequest.user_id == user_id)

    if status:
        query = query.where(VacationRequest.status == status)

    query = (
        query.order_by(VacationRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await session.execute(query)
    requests = result.scalars().all()

    return [
        VacationRequestListItem(
            id=r.id,
            user_id=r.user_id,
            user_name=r.user.name if r.user else 'Desconhecido',
            target_accrual_period_id=r.target_accrual_period_id,
            status=r.status,
            requested_at=r.requested_at,
            total_days=sum(p.days_count for p in r.periods),
            periods_count=len(r.periods),
            created_at=r.created_at,
        )
        for r in requests
    ]


@router.get(
    '/requests/by-sector/{setor}',
    response_model=list[VacationRequestListItem],
)
async def list_vacation_requests_by_sector(  # noqa: PLR0913, PLR0917
    setor: Setor,
    session: Session,
    current_user: VerifyAdminCoord,
    subsetor: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[VacationRequestStatus], Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Lista solicitações de férias dos empregados de um setor/subsetor."""
    query = (
        select(VacationRequest)
        .options(selectinload(VacationRequest.user))
        .join(User, VacationRequest.user_id == User.id)
        .where(User.setor == setor)
    )
    if subsetor:
        query = query.where(User.subsetor == subsetor)
    if status:
        query = query.where(VacationRequest.status == status)
    query = (
        query.order_by(VacationRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(query)
    requests = result.scalars().all()
    return [
        VacationRequestListItem(
            id=r.id,
            user_id=r.user_id,
            user_name=r.user.name if r.user else 'Desconhecido',
            target_accrual_period_id=r.target_accrual_period_id,
            status=r.status,
            requested_at=r.requested_at,
            total_days=sum(p.days_count for p in r.periods),
            periods_count=len(r.periods),
            created_at=r.created_at,
        )
        for r in requests
    ]


@router.get('/requests/{request_id}', response_model=VacationRequestRead)
async def get_vacation_request(
    request_id: int,
    session: Session,
    current_user: CurrentUser,
):
    request = await _load_request_with_relations(session, request_id)
    if not request:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Solicitação não encontrada',
        )
    if request.user_id != current_user.id and current_user.role not in {
        'admin',
        'coord',
    }:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Acesso negado: usuário sem permissão',
        )
    return _request_read(request)


@router.post(
    '/requests/{request_id}/approve', response_model=VacationRequestRead
)
async def approve_vacation_request(
    request_id: int,
    data: VacationReviewRequest,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    request = await _load_request_with_relations(session, request_id)
    if not request:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Solicitação não encontrada',
        )
    try:
        request = await service.approve_request(
            request, current_user, data.reviewer_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    await session.commit()
    request = await _load_request_with_relations(session, request.id)
    return _request_read(request)


@router.post(
    '/requests/{request_id}/reject', response_model=VacationRequestRead
)
async def reject_vacation_request(
    request_id: int,
    data: VacationReviewRequest,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    request = await _load_request_with_relations(session, request_id)
    if not request:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Solicitação não encontrada',
        )
    try:
        request = await service.reject_request(
            request, current_user, data.reviewer_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    await session.commit()
    request = await _load_request_with_relations(session, request.id)
    return _request_read(request)


@router.post(
    '/requests/{request_id}/cancel', response_model=VacationRequestRead
)
async def cancel_vacation_request(
    request_id: int,
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    request = await _load_request_with_relations(session, request_id)
    if not request:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Solicitação não encontrada',
        )
    try:
        request = await service.cancel_request(request, current_user)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    await session.commit()
    request = await _load_request_with_relations(session, request.id)
    return _request_read(request)


# --- Grants ---


@router.get('/grants', response_model=list[VacationGrantRead])
async def list_vacation_grants(  # noqa: PLR0913, PLR0917
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
    status: Annotated[Optional[VacationGrantStatus], Query()] = None,
    user_id: Annotated[Optional[int], Query()] = None,
    accrual_period_id: Annotated[Optional[int], Query()] = None,
):
    if current_user.role not in {'admin', 'coord'}:
        user_id = current_user.id
    try:
        grants = await service.list_grants(
            user_id=user_id,
            status=status,
            accrual_period_id=accrual_period_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    return [_grant_read(g) for g in grants]


@router.get(
    '/grants/by-sector/{setor}', response_model=list[VacationGrantRead]
)
async def list_vacation_grants_by_sector(  # noqa: PLR0913, PLR0917
    setor: Setor,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
    subsetor: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[VacationGrantStatus], Query()] = None,
    accrual_period_id: Annotated[Optional[int], Query()] = None,
):
    """Lista concessões de férias dos empregados de um setor/subsetor."""
    grants = await service.list_grants(
        status=status,
        accrual_period_id=accrual_period_id,
        setor=setor,
        subsetor=subsetor,
    )
    return [_grant_read(g) for g in grants]


@router.get('/grants/{grant_id}', response_model=VacationGrantRead)
async def get_vacation_grant(
    grant_id: int,
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    grant = await service.get_grant(grant_id)
    if not grant:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Concessão não encontrada',
        )
    if grant.user_id != current_user.id and current_user.role not in {
        'admin',
        'coord',
    }:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Acesso negado: usuário sem permissão',
        )
    return _grant_read(grant)


@router.post(
    '/grants/{grant_id}/confirm-fruition',
    response_model=VacationGrantRead,
)
async def confirm_grant_fruition(
    grant_id: int,
    data: VacationConfirmFruitionRequest,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    """RH confirma (ou não) a fruição efetiva de uma concessão."""
    grant = await service.get_grant(grant_id)
    if not grant:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Concessão não encontrada',
        )
    try:
        grant = await service.confirm_fruition(
            grant, current_user, data.confirm, data.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    await session.commit()
    await session.refresh(grant)
    return _grant_read(grant)


# --- Preview e alertas ---


@router.post('/preview', response_model=VacationPreviewResponse)
async def preview_vacation(
    data: VacationPreviewRequest,
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    return await service.preview_vacation(current_user, data)


@router.get('/alerts', response_model=list[VacationAccrualPeriodAlert])
async def vacation_alerts(
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    """Alertas de férias: vencidos, prestes a vencer e pendentes."""
    alerts = await service.get_vacation_alerts()
    await session.commit()
    return alerts
