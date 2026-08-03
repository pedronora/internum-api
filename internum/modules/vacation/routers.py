from datetime import date
from http import HTTPStatus
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import get_session
from internum.core.permissions import (
    CurrentUser,
    VerifyAdmin,
    VerifyAdminCoord,
    VerifySelfAdminCoord,
)
from internum.modules.users.models import User
from internum.modules.vacation.enums import VacationRequestStatus
from internum.modules.vacation.models import (
    VacationPeriod,
    VacationRequest,
)
from internum.modules.vacation.schemas import (
    VacationApprovalRequest,
    VacationBalanceAdjustRequest,
    VacationBalanceRead,
    VacationPeriodCreate,
    VacationPreviewRequest,
    VacationPreviewResponse,
    VacationRequestCreate,
    VacationRequestListItem,
    VacationRequestRead,
    VacationRequestUpdate,
    VacationSellDaysRequest,
)
from internum.modules.vacation.services import CLTVacationService

router = APIRouter(prefix='/vacation', tags=['Vacation'])

Session = Annotated[AsyncSession, Depends(get_session)]


def get_vacation_service(session: Session) -> CLTVacationService:
    return CLTVacationService(session)


@router.get('/balance', response_model=VacationBalanceRead)
async def get_my_balance(
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    balance = await service.calculate_balance(current_user)
    return balance


@router.get('/balance/{user_id}', response_model=VacationBalanceRead)
async def get_user_balance(
    user_id: int,
    session: Session,
    current_user: VerifyAdminCoord,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    user = await session.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Usuário não encontrado'
        )
    balance = await service.calculate_balance(user)
    return balance


@router.post('/preview', response_model=VacationPreviewResponse)
async def preview_vacation(
    data: VacationPreviewRequest,
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    return await service.preview_vacation(current_user, data)


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
    request = await service.create_request(current_user, data.periods)
    await session.commit()
    return await _load_request_with_relations(session, request.id)


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

    query = query.order_by(
        VacationRequest.created_at.desc()
    ).offset(skip).limit(limit)

    result = await session.execute(query)
    requests = result.scalars().all()

    return [
        VacationRequestListItem(
            id=r.id,
            user_id=r.user_id,
            user_name=r.user.name if r.user else 'Desconhecido',
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
    current_user: VerifySelfAdminCoord,
):
    request = await _load_request_with_relations(session, request_id)
    if not request:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Solicitação não encontrada',
        )
    return request


@router.put('/requests/{request_id}', response_model=VacationRequestRead)
async def update_vacation_request(
    request_id: int,
    data: VacationRequestUpdate,
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

    if request.user_id != current_user.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Não pode editar solicitação de outro usuário',
        )

    if request.status != VacationRequestStatus.DRAFT:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Solicitação não está em rascunho',
        )

    if data.periods is not None:
        preview = await service.preview_vacation(
            current_user, VacationPreviewRequest(periods=data.periods)
        )
        if not preview.valid:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail='; '.join(preview.errors),
            )

        for period in request.periods:
            await session.delete(period)
        await session.flush()

        for period_data in data.periods:
            cal_days = service.count_calendar_days(
                period_data.start_date, period_data.end_date
            )
            work_days = service.count_working_days(
                period_data.start_date, period_data.end_date
            )
            period_type = (
                'full'
                if cal_days >= service.MIN_MAIN_PERIOD_DAYS
                else 'proportional'
            )

            period = VacationPeriod(
                request_id=request.id,
                start_date=period_data.start_date,
                end_date=period_data.end_date,
                period_type=period_type,
                status='pending',
                days_count=cal_days,
                working_days_count=work_days,
            )
            session.add(period)

    if data.reviewer_notes is not None:
        request.reviewer_notes = data.reviewer_notes

    await session.commit()
    return await _load_request_with_relations(session, request.id)


@router.post(
    '/requests/{request_id}/submit', response_model=VacationRequestRead
)
async def submit_vacation_request(
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

    if request.user_id != current_user.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Não pode submeter solicitação de outro usuário',
        )

    if request.status != VacationRequestStatus.DRAFT:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Solicitação já foi submetida',
        )

    preview = await service.preview_vacation(
        current_user,
        VacationPreviewRequest(
            periods=[
                VacationPeriodCreate(
                    start_date=p.start_date,
                    end_date=p.end_date,
                    period_type=p.period_type,
                )
                for p in request.periods
            ]
        ),
    )
    if not preview.valid:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='; '.join(preview.errors),
        )

    request.status = VacationRequestStatus.SUBMITTED
    request.requested_at = date.today()

    for period in request.periods:
        period.status = 'pending'

    await session.commit()
    return await _load_request_with_relations(session, request.id)


@router.post(
    '/requests/{request_id}/approve', response_model=VacationRequestRead
)
async def approve_vacation_request(
    request_id: int,
    data: VacationApprovalRequest,
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

    if data.action != 'approve':
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Ação deve ser "approve"',
        )

    try:
        request = await service.approve_request(
            request, current_user, data.reviewer_notes
        )
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(e)
        )

    if data.periods:
        for i, period_update in enumerate(data.periods):
            if i < len(request.periods):
                period = request.periods[i]
                update_data = period_update.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    if value is not None:
                        setattr(period, field, value)

    await session.commit()
    return await _load_request_with_relations(session, request.id)


@router.post(
    '/requests/{request_id}/reject', response_model=VacationRequestRead
)
async def reject_vacation_request(
    request_id: int,
    data: VacationApprovalRequest,
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

    if data.action != 'reject':
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Ação deve ser "reject"',
        )

    try:
        request = await service.reject_request(
            request, current_user, data.reviewer_notes
        )
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(e)
        )

    await session.commit()
    return await _load_request_with_relations(session, request.id)


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
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(e)
        )

    await session.commit()
    return await _load_request_with_relations(session, request.id)


@router.post('/sell-days', response_model=VacationBalanceRead)
async def sell_vacation_days(
    data: VacationSellDaysRequest,
    session: Session,
    current_user: CurrentUser,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    try:
        balance = await service.sell_vacation_days(current_user, data.days)
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(e)
        )

    await session.commit()
    return balance


@router.put('/balance/{user_id}/adjust', response_model=VacationBalanceRead)
async def adjust_vacation_balance(
    user_id: int,
    data: VacationBalanceAdjustRequest,
    session: Session,
    current_user: VerifyAdmin,
    service: Annotated[CLTVacationService, Depends(get_vacation_service)],
):
    """Ajuste manual de saldo (apenas admin) - para migração/histórico."""
    user = await session.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Usuário não encontrado',
        )

    try:
        balance = await service.adjust_balance(
            user,
            current_user,
            data.manual_adjustment_days,
            data.adjustment_reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(e)
        )

    await session.commit()
    return balance


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
