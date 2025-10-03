import math
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import not_

from internum.core.database import get_session
from internum.core.permissions import (
    CurrentUser,
    VerifyAdminCoord,
)
from internum.modules.notices.models import Notice, NoticeRead
from internum.modules.notices.schemas import (
    Message,
    NoticeCreate,
    NoticeDetail,
    NoticeQueryParams,
    NoticeSchema,
    PageMeta,
    PaginatedNoticeList,
)
from internum.modules.users.models import User

router = APIRouter(prefix='/notices', tags=['Notices'])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get('/unreads/me', response_model=PaginatedNoticeList)
async def list_unread_notices(
    session: Session,
    params: Annotated[NoticeQueryParams, Depends()],
    current_user: CurrentUser,
):
    limit = max(1, params.limit)
    offset = max(0, params.offset)
    search = params.search

    filters = [Notice.active]

    unread_filter = not_(
        Notice.reads.any(NoticeRead.user_id == current_user.id)
    )
    filters.append(unread_filter)

    if search:
        search_pattern = f'%{search}%'
        search_filters = or_(
            Notice.title.ilike(search_pattern),
            Notice.content.ilike(search_pattern),
            Notice.user.has(User.name.ilike(search_pattern)),
        )
        filters.append(search_filters)

    total: int = (
        await session.scalar(
            select(func.count()).select_from(Notice).where(*filters)
        )
        | 0
    )

    query = await session.scalars(
        select(Notice)
        .options(selectinload(Notice.user))
        .where(*filters)
        .order_by(Notice.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    notices = query.all()

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

    return {'meta': meta, 'notices': notices}


@router.get('/reads/me', response_model=PaginatedNoticeList)
async def list_read_notices(
    session: Session,
    params: Annotated[NoticeQueryParams, Depends()],
    current_user: CurrentUser,
):
    limit = max(1, params.limit)
    offset = max(0, params.offset)
    search = params.search

    filters = [Notice.active]

    unread_filter = Notice.reads.any(NoticeRead.user_id == current_user.id)

    filters.append(unread_filter)

    if search:
        search_pattern = f'%{search}%'
        search_filters = or_(
            Notice.title.ilike(search_pattern),
            Notice.content.ilike(search_pattern),
            Notice.user.has(User.name.ilike(search_pattern)),
        )
        filters.append(search_filters)

    total: int = (
        await session.scalar(
            select(func.count()).select_from(Notice).where(*filters)
        )
        | 0
    )

    query = await session.scalars(
        select(Notice)
        .options(selectinload(Notice.user))
        .where(*filters)
        .order_by(Notice.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    notices = query.all()

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

    return {'meta': meta, 'notices': notices}


@router.post(
    '/{notice_id}/mark-read/me',
    status_code=HTTPStatus.OK,
    response_model=Message,
    responses={
        HTTPStatus.NOT_FOUND: {
            'description': 'Notice with id (id) not found.'
        },
        HTTPStatus.CONFLICT: {
            'description': 'Notice with id (id) '
            'is already marked as read by user (id).'
        },
    },
)
async def mark_as_read(
    notice_id: int, session: Session, current_user: CurrentUser
):
    db_notice = await session.scalar(
        select(Notice)
        .where((Notice.id == notice_id) & (Notice.active))
        .options(selectinload(Notice.user))
    )

    if not db_notice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Notice with id ({notice_id}) not found.',
        )

    read_record = await session.scalar(
        select(NoticeRead).where(
            NoticeRead.user_id == current_user.id,
            NoticeRead.notice_id == notice_id,
        )
    )

    if read_record:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f'Notice with id ({notice_id}) '
            f'is already marked as read by user ({current_user.id}).',
        )

    new_read = NoticeRead(user_id=current_user.id, notice_id=notice_id)

    session.add(new_read)
    await session.commit()

    return {
        'message': f'Notice with id ({notice_id}) '
        f'was marked read by user ({current_user.id}).'
    }


@router.post('/', response_model=NoticeSchema, status_code=HTTPStatus.CREATED)
async def create_notice(
    notice: NoticeCreate,
    session: Session,
    author: VerifyAdminCoord,
):
    db_notice = Notice(
        title=notice.title, content=notice.content, user_id=author.id
    )
    session.add(db_notice)
    await session.commit()
    await session.refresh(db_notice)
    return db_notice


@router.get('/', response_model=PaginatedNoticeList)
async def list_notices(
    session: Session,
    params: Annotated[NoticeQueryParams, Depends()],
    current_user: CurrentUser,
):
    limit = max(1, params.limit)
    offset = max(0, params.offset)
    search = params.search

    filters = [Notice.active]

    if search:
        search_pattern = f'%{search}%'

        search_filters = or_(
            Notice.title.ilike(search_pattern),
            Notice.content.ilike(search_pattern),
            Notice.user.has(User.name.ilike(search_pattern)),
        )
        filters.append(search_filters)

    total: int = (
        await session.scalar(
            select(func.count()).select_from(Notice).where(*filters)
        )
        | 0
    )

    query = await session.scalars(
        select(Notice)
        .options(selectinload(Notice.user))
        .where(*filters)
        .order_by(Notice.created_at)
        .offset(offset)
        .limit(limit)
    )
    notices = query.all()

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

    return {'meta': meta, 'notices': notices}


@router.get(
    '/{notice_id}',
    response_model=NoticeDetail,
    status_code=HTTPStatus.OK,
    responses={
        HTTPStatus.NOT_FOUND: {
            'description': 'Notice with id (id) not found.'
        },
    },
)
async def get_notice_by_id(
    notice_id: int, session: Session, current_user: CurrentUser
):
    db_notice = await session.scalar(
        select(Notice)
        .where((Notice.id == notice_id) & (Notice.active))
        .options(selectinload(Notice.user))
        .options(selectinload(Notice.reads).selectinload(NoticeRead.user))
    )

    if not db_notice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Notice with id ({notice_id}) not found.',
        )

    return db_notice


@router.delete(
    '/{notice_id}',
    status_code=HTTPStatus.NO_CONTENT,
    responses={
        HTTPStatus.BAD_REQUEST: {
            'description': 'The notice with id (id) is already inactive.'
        },
    },
)
async def deactivate_notice(
    notice_id: int,
    session: Session,
    current_user: VerifyAdminCoord,
):
    db_notice = await session.scalar(
        select(Notice).where(Notice.id == notice_id)
    )

    if not db_notice.active:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f'The notice with id ({notice_id}) is already inactive.',
        )

    db_notice.active = False
    await session.commit()
