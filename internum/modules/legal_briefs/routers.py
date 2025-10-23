import math
from datetime import datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import get_session
from internum.core.permissions import CurrentUser, VerifyAdmin
from internum.modules.legal_briefs.models import LegalBrief, LegalBriefRevision
from internum.modules.legal_briefs.schemas import (
    LegalBriefCreate,
    LegalBriefQueryParams,
    LegalBriefSchema,
    LegalBriefUpdate,
    PageMeta,
    PaginatedLegalBriefList,
)

router = APIRouter(prefix='/legal-briefs', tags=['Legal Briefs'])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    '/', response_model=LegalBriefSchema, status_code=HTTPStatus.CREATED
)
async def create_legal_brief(
    legal_brief: LegalBriefCreate, session: Session, user: VerifyAdmin
):
    db_legal_brief = LegalBrief(
        title=legal_brief.title,
        content=legal_brief.content,
        created_by_id=user.id,
    )

    try:
        session.add(db_legal_brief)
        await session.commit()
        await session.refresh(db_legal_brief)
    except Exception:
        await session.rollback()
        raise

    return db_legal_brief


@router.get('/', response_model=PaginatedLegalBriefList)
async def list_legal_briefs(
    session: Session,
    params: Annotated[LegalBriefQueryParams, Depends()],
    current_user: CurrentUser,
):
    limit = max(1, params.limit)
    offset = max(0, params.offset)
    search = params.search

    filters = []

    if search:
        search_pattern = f'%{search}%'
        filters.append(
            or_(
                LegalBrief.title.ilike(search_pattern),
                LegalBrief.content.ilike(search_pattern),
            )
        )

    count_stmt = select(func.count()).select_from(LegalBrief)
    if filters:
        count_stmt = count_stmt.where(*filters)

    total: int = (await session.scalar(count_stmt)) or 0

    query_stmt = (
        select(LegalBrief)
        .order_by(LegalBrief.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    if filters:
        query_stmt = query_stmt.where(*filters)

    query = await session.scalars(query_stmt)
    legal_briefs = query.all()

    total_pages = math.ceil(total / limit) if limit > 0 else 1
    page = (offset // limit) + 1 if limit > 0 else 1
    has_next = (offset + limit) < total
    has_prev = offset > 0

    meta = PageMeta(
        total=total,
        page=page,
        size=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
        offset=offset,
    )

    return {'meta': meta, 'legal_briefs': legal_briefs}


@router.get(
    '/{legal_brief_id}',
    response_model=LegalBriefSchema,
    status_code=HTTPStatus.OK,
    responses={
        HTTPStatus.NOT_FOUND: {
            'description': 'Legal Brief with id (id) not found.'
        },
    },
)
async def get_legal_brief_by_id(
    legal_brief_id: int, session: Session, current_user: CurrentUser
):
    db_legal_brief = await session.scalar(
        select(LegalBrief)
        .options(
            selectinload(LegalBrief.created_by),
            selectinload(LegalBrief.updated_by),
            selectinload(LegalBrief.canceled_by),
            selectinload(LegalBrief.revisions),
        )
        .where(LegalBrief.id == legal_brief_id)
    )

    if not db_legal_brief:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Legal Brief with id ({legal_brief_id}) not found.',
        )

    return db_legal_brief


@router.put(
    '/{legal_brief_id}',
    status_code=HTTPStatus.OK,
    response_model=LegalBriefSchema,
    responses={
        HTTPStatus.NOT_FOUND: {'description': 'Legal Brief not found.'},
        HTTPStatus.BAD_REQUEST: {
            'description': 'This Legal Brief has already been canceled.'
        },
    },
)
async def update_legal_brief(
    legal_brief_id: int,
    data: LegalBriefUpdate,
    session: Session,
    current_user: VerifyAdmin,
):
    current_brief = await session.scalar(
        select(LegalBrief).where(LegalBrief.id == legal_brief_id)
    )

    if not current_brief:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='LegalBrief not found',
        )

    if current_brief.canceled:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='This Legal Brief has already been canceled.',
        )

    try:
        revision = LegalBriefRevision(
            brief_id=current_brief.id,
            content=current_brief.content,
            updated_by_id=current_user.id,
        )
        session.add(revision)

        current_brief.title = data.title or current_brief.title
        current_brief.content = data.content or current_brief.content
        current_brief.updated_by_id = current_user.id
        current_brief.updated_at = datetime.utcnow()
        session.add(current_brief)

        await session.commit()
        await session.refresh(current_brief)
    except Exception:
        await session.rollback()
        raise

    return current_brief


@router.patch(
    '/{legal_brief_id}/cancel',
    response_model=LegalBriefSchema,
    status_code=HTTPStatus.OK,
    responses={
        HTTPStatus.NOT_FOUND: {'description': 'Legal Brief not found.'},
        HTTPStatus.BAD_REQUEST: {
            'description': 'This Legal Brief has already been canceled.'
        },
    },
)
async def cancel_legal_brief(
    legal_brief_id: int,
    session: Session,
    current_user: CurrentUser,
):
    db_legal_brief = await session.scalar(
        select(LegalBrief)
        .options(
            selectinload(LegalBrief.created_by),
            selectinload(LegalBrief.updated_by),
            selectinload(LegalBrief.canceled_by),
            selectinload(LegalBrief.revisions),
        )
        .where(LegalBrief.id == legal_brief_id)
    )

    if not db_legal_brief:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Legal Brief with id ({legal_brief_id}) not found.',
        )

    if db_legal_brief.canceled:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='This Legal Brief has already been canceled.',
        )

    db_legal_brief.canceled = True
    db_legal_brief.canceled_by_id = current_user.id

    await session.commit()
    await session.refresh(db_legal_brief)

    return db_legal_brief
