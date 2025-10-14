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
    user_id = 1


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
    session.add_all(NoticeFactory.create_batch(5, user_id=user_admin.id))
    await session.commit()

    response = client.get(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert len(response.json()['notices']) == expected_notices


@pytest.mark.asyncio
async def test_list_unreads_notices_should_return_5(
    session, client, user, token
):
    expected_notices = 5
    session.add_all(NoticeFactory.create_batch(5, user_id=user.id))
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
    notice_match = NoticeFactory.create(
        title='Aviso importante sobre sistema', user_id=user_admin.id
    )
    notice_other = NoticeFactory.create(
        title='Outro título', user_id=user_admin.id
    )
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
    expected_notices = 5
    session.add_all(NoticeFactory.create_batch(10, user_id=user_admin.id))
    await session.commit()

    response = client.get(
        ENDPOINT_URL + '?limit=5&offset=5',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    data = response.json()
    assert response.status_code == HTTPStatus.OK
    assert len(data['notices']) == expected_notices


@pytest.mark.asyncio
async def test_list_unreads_when_no_unread_notices(
    session, client, user, token
):
    notices = NoticeFactory.create_batch(3, user_id=user.id)
    session.add_all(notices)
    await session.commit()

    session.add_all([
        NoticeRead(user_id=user.id, notice_id=n.id) for n in notices
    ])
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
        Notice(user_id=user.id, title='Aviso 1', content='Teste'),
        Notice(user_id=user.id, title='Aviso 2', content='Teste'),
    ]
    session.add_all(notices)
    await session.commit()

    read = NoticeRead(user_id=user.id, notice_id=notices[0].id)
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
    notice1 = Notice(user_id=user.id, title='Importante', content='Urgente')
    notice2 = Notice(
        user_id=user.id, title='Comunicado geral', content='Texto genérico'
    )
    session.add_all([notice1, notice2])
    await session.commit()

    session.add_all([
        NoticeRead(user_id=user.id, notice_id=n.id) for n in [notice1, notice2]
    ])
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
async def test_get_notice_by_id(session, client, user, token):
    session.add(NoticeFactory.create(user_id=user.id))
    await session.commit()

    id = 1

    response = client.get(
        ENDPOINT_URL + f'/{id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == id


@pytest.mark.asyncio
async def test_get_notice_not_found(client, token_admin):
    response = client.get(
        ENDPOINT_URL + '/999',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_mark_notice_as_read(session, client, user, token):
    notice = NoticeFactory.create(user_id=user.id)
    session.add(notice)
    await session.commit()

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
    session, client, user, token
):
    notice = NoticeFactory(user_id=user.id)
    session.add(notice)
    await session.commit()

    session.add(NoticeRead(user_id=user.id, notice_id=notice.id))
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
        user_id=user_admin.id,
        title='Aviso inativo',
        content='...',
        active=False,
    )
    session.add(notice)
    await session.commit()

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
    notice = Notice(
        user_id=user_admin.id, title='Aviso ativo', content='Conteúdo'
    )
    session.add(notice)
    await session.commit()

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
