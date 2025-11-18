from http import HTTPStatus

import factory.fuzzy
import pytest

from internum.modules.notices.models import Notice, NoticeRead

ENDPOINT_URL = '/api/v1/notices'


class NoticeFactory(factory.Factory):
    class Meta:
        model = Notice

    title = factory.Faker('text')
    content = factory.Faker('text')


def test_create_notice(client, user_admin, token_admin):
    new_notice = {'title': 'Aviso teste', 'content': 'Conteúdo do aviso teste'}

    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
        json=new_notice,
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['title'] == new_notice['title']
    assert response.json()['content'] == new_notice['content']
    assert response.json()['author']['name'] == user_admin.name


def test_create_notice_without_permission(client, user, token):
    new_notice = {'title': 'Aviso teste', 'content': 'Conteúdo do aviso teste'}

    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token}'},
        json=new_notice,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_create_notice_value_missing(client, user_admin, token_admin):
    new_notice = {'title': '', 'content': 'Conteúdo do aviso teste'}

    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
        json=new_notice,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_notice_data_missing_field(client, user_admin, token_admin):
    new_notice = {'content': 'Conteúdo do aviso teste'}

    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
        json=new_notice,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert any(
        'field required' in error.get('msg', '').lower()
        for error in response.json()['detail']
    )


@pytest.mark.asyncio
async def test_list_notices_should_return_5(
    session, client, user_admin, token_admin
):
    expected_notices = 5
    user_id = user_admin.id

    notices_list = NoticeFactory.create_batch(5)

    for notice in notices_list:
        notice.created_by_id = user_id

    session.add_all(notices_list)
    await session.commit()

    response = client.get(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert len(response.json()['notices']) == expected_notices


@pytest.mark.asyncio
async def test_list_unreads_notices_should_return_5(
    session, client, user, user_admin, token
):
    expected_notices = 5
    user_id = user_admin.id

    notices_list = NoticeFactory.create_batch(5)

    for notice in notices_list:
        notice.created_by_id = user_id

    session.add_all(notices_list)
    await session.commit()

    response = client.get(
        ENDPOINT_URL + '/unreads/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert len(response.json()['notices']) == expected_notices


@pytest.mark.asyncio
async def test_list_notices_with_search_filter(
    session, client, user_admin, token_admin
):
    notice_match = NoticeFactory.create(title='Aviso importante sobre sistema')
    notice_other = NoticeFactory.create(title='Outro título')
    notice_match.created_by_id = notice_other.created_by_id = user_admin.id

    session.add_all([notice_match, notice_other])
    await session.commit()

    response = client.get(
        ENDPOINT_URL + '?search=sistema',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    data = response.json()
    assert response.status_code == HTTPStatus.OK
    assert len(data['notices']) == 1
    assert data['notices'][0]['id'] == notice_match.id


@pytest.mark.asyncio
async def test_list_notices_with_pagination(
    session, client, user_admin, token_admin
):
    pagination = 5
    total = 10

    notices_list = NoticeFactory.create_batch(total)

    for notice in notices_list:
        notice.created_by_id = user_admin.id

    session.add_all(notices_list)
    await session.commit()

    response = client.get(
        ENDPOINT_URL + f'?limit=5&offset={pagination}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    data = response.json()
    assert response.status_code == HTTPStatus.OK
    assert data['meta']['total'] == total
    assert len(data['notices']) == pagination


@pytest.mark.asyncio
async def test_list_unreads_when_no_unread_notices(
    session, client, user, user_admin, token
):
    notices_list = NoticeFactory.create_batch(3)
    for notice in notices_list:
        notice.created_by_id = user_admin.id

    session.add_all(notices_list)
    await session.commit()

    notices_read_list = [NoticeRead(notice_id=n.id) for n in notices_list]
    for notice in notices_read_list:
        notice.created_by_id = user.id

    session.add_all(notices_read_list)
    await session.commit()

    response = client.get(
        ENDPOINT_URL + '/unreads/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    data = response.json()
    assert response.status_code == HTTPStatus.OK
    assert len(data['notices']) == 0


@pytest.mark.asyncio
async def test_list_read_notices_returns_only_user_reads(
    session, client, user, token
):
    notices = [
        Notice(title='Aviso 1', content='Teste'),
        Notice(title='Aviso 2', content='Teste'),
    ]

    for notice in notices:
        notice.created_by_id = user.id

    session.add_all(notices)
    await session.commit()

    read = NoticeRead(notice_id=notices[0].id)
    read.created_by_id = user.id
    session.add(read)
    await session.commit()

    response = client.get(
        f'{ENDPOINT_URL}/reads/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    data = response.json()
    assert response.status_code == HTTPStatus.OK
    assert len(data['notices']) == 1
    assert data['notices'][0]['id'] == notices[0].id


@pytest.mark.asyncio
async def test_list_read_notices_with_search_filter(
    session, client, user, token
):
    notice1 = Notice(title='Importante', content='Urgente')
    notice1.created_by_id = user.id
    notice2 = Notice(title='Comunicado geral', content='Texto genérico')
    notice2.created_by_id = user.id

    session.add_all([notice1, notice2])
    await session.commit()

    read_notices_list = []
    for notice in [notice1, notice2]:
        read = NoticeRead(notice_id=notice.id)
        read.created_by_id = user.id
        read_notices_list.append(read)

    session.add_all(read_notices_list)
    await session.commit()

    response = client.get(
        f'{ENDPOINT_URL}/reads/me?search=Importante',
        headers={'Authorization': f'Bearer {token}'},
    )

    data = response.json()
    assert response.status_code == HTTPStatus.OK
    assert data['meta']['total'] == 1
    assert all('Importante' in n['title'] for n in data['notices'])


def test_list_notices_unauthorized(client):
    response = client.get(ENDPOINT_URL)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_notice_by_id(session, client, user, user_admin, token):
    notice = NoticeFactory.create()
    notice.created_by_id = user_admin.id
    session.add(notice)
    await session.commit()
    await session.refresh(notice)

    id = notice.id

    response = client.get(
        ENDPOINT_URL + f'/{id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == id


@pytest.mark.asyncio
async def test_get_notice_not_found(client, token_admin):
    response = client.get(
        ENDPOINT_URL + '/9909',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_mark_notice_as_read(session, client, user, user_admin, token):
    notice = NoticeFactory.create()
    notice.created_by_id = user_admin.id
    session.add(notice)
    await session.commit()
    await session.refresh(notice)

    response = client.post(
        f'{ENDPOINT_URL}/{notice.id}/mark-read/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK

    unread_response = client.get(
        ENDPOINT_URL + '/unreads/me',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert all(n['id'] != notice.id for n in unread_response.json()['notices'])


@pytest.mark.asyncio
async def test_mark_read_returns_404_when_notice_not_found(client, token):
    invalid_notice_id = 9999

    response = client.post(
        ENDPOINT_URL + f'/{invalid_notice_id}/mark-read/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'not found' in response.json()['detail']


@pytest.mark.asyncio
async def test_mark_read_returns_409_when_already_marked_read(
    session, client, user, user_admin, token
):
    notice = NoticeFactory()
    notice.created_by_id = user_admin.id
    session.add(notice)
    await session.commit()
    await session.refresh(notice)

    notice_read = NoticeRead(notice_id=notice.id)
    notice_read.created_by_id = user.id
    session.add(notice_read)
    await session.commit()

    response = client.post(
        ENDPOINT_URL + f'/{notice.id}/mark-read/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert 'already marked as read' in response.json()['detail']


@pytest.mark.asyncio
async def test_deactivate_notice_already_inactive(
    session, client, token_admin, user_admin
):
    notice = Notice(
        title='Aviso inativo',
        content='...',
        active=False,
    )
    notice.created_by_id = user_admin.id
    session.add(notice)
    await session.commit()
    await session.refresh(notice)

    response = client.delete(
        f'{ENDPOINT_URL}/{notice.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_invalid_route_returns_404(client, token_admin):
    response = client.get(
        ENDPOINT_URL + '/nonexistent-route',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_deactivate_notice_success(
    session, client, token_admin, user_admin
):
    notice = Notice(title='Aviso ativo', content='Conteúdo')
    notice.created_by_id = user_admin.id
    session.add(notice)
    await session.commit()
    await session.refresh(notice)

    response = client.delete(
        f'{ENDPOINT_URL}/{notice.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NO_CONTENT

    db_notice = await session.get(Notice, notice.id)
    assert db_notice.active is False


@pytest.mark.asyncio
async def test_deactivate_notice_not_found(session, client, token_admin):
    response = client.delete(
        f'{ENDPOINT_URL}/9999',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
