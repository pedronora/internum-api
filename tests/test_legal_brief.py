from datetime import datetime
from http import HTTPStatus

import factory.fuzzy
import pytest

from internum.modules.legal_briefs.models import LegalBrief

ENDPOINT_URL = '/api/v1/legal-briefs'


class LegalBriefFactory(factory.Factory):
    class Meta:
        model = LegalBrief

    title = factory.Faker('text')
    content = factory.Faker('text')
    created_by_id = 1


def test_create_legal_brief(client, user_admin, token_admin):
    new_legal_brief = {
        'title': 'Ementa teste',
        'content': 'Conteúdo da ementa teste',
    }

    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
        json=new_legal_brief,
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['title'] == new_legal_brief['title']
    assert response.json()['content'] == new_legal_brief['content']
    assert response.json()['created_by']['name'] == user_admin.name


def test_create_legal_brief_without_permission(client, user, token):
    new_legal_brief = {
        'title': 'Ementa teste',
        'content': 'Conteúdo da ementa teste',
    }

    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token}'},
        json=new_legal_brief,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_create_legal_brief_value_missing(client, user_admin, token_admin):
    new_legal_brief = {
        'title': '',
        'content': 'Conteúdo da ementa teste',
    }

    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
        json=new_legal_brief,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_legal_brief_data_missing_field(
    client, user_admin, token_admin
):
    new_legal_brief = {
        'content': 'Conteúdo da ementa teste',
    }

    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
        json=new_legal_brief,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert any(
        'field required' in error.get('msg', '').lower()
        for error in response.json()['detail']
    )


@pytest.mark.asyncio
async def test_list_legal_briefs(session, client, user, token):
    total = 5

    legal_briefs = LegalBriefFactory.create_batch(total, created_by_id=user.id)
    session.add_all(legal_briefs)
    await session.commit()

    response = client.get(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['meta']['total'] == total


@pytest.mark.asyncio
async def test_list_legal_briefs_with_search_param(
    session, client, user, token
):
    legal_briefs = LegalBriefFactory.create_batch(3, created_by_id=user.id)
    custom_legal_brief = LegalBriefFactory.create(title='Busca')
    legal_briefs.append(custom_legal_brief)

    session.add_all(legal_briefs)
    await session.commit()

    response = client.get(
        ENDPOINT_URL + '?limit=10&offset=0&search=busca',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['meta']['total'] >= 1


@pytest.mark.asyncio
async def test_get_legal_brief_by_id_success(
    client,
    session,
    user_admin,
    token_admin,
):
    legal_brief = LegalBriefFactory(created_by_id=user_admin.id)
    session.add(legal_brief)
    await session.commit()
    await session.refresh(legal_brief)

    response = client.get(
        ENDPOINT_URL + f'/{legal_brief.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data['id'] == legal_brief.id
    assert data['title'] == legal_brief.title
    assert data['content'] == legal_brief.content
    assert data['created_by']['id'] == user_admin.id
    assert data['canceled'] is False
    assert data['revisions'] == [] or data['revisions'] is None


def test_get_legal_brief_by_id_not_found(client, token_admin):
    response = client.get(
        ENDPOINT_URL + '/99999',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'not found' in response.json()['detail'].lower()


@pytest.mark.asyncio
async def test_update_legal_brief_creates_revision(
    session, client, user_admin, token_admin
):
    brief = LegalBrief(
        title='Original',
        content='Conteúdo inicial',
        created_by_id=user_admin.id,
    )
    session.add(brief)
    await session.commit()
    await session.refresh(brief)

    response = client.put(
        ENDPOINT_URL + f'/{brief.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
        json={'title': 'Novo título', 'content': 'Novo conteúdo'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['title'] == 'Novo título'
    assert data['content'] == 'Novo conteúdo'

    revisions = data['revisions']

    assert revisions is not None
    assert revisions[0]['content'] == 'Conteúdo inicial'


def test_update_legal_brief_not_found(session, client, token_admin):
    response = client.put(
        ENDPOINT_URL + '/9999',
        headers={'Authorization': f'Bearer {token_admin}'},
        json={'title': 'Novo título', 'content': 'Novo content'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail'] == 'LegalBrief not found'


@pytest.mark.asyncio
async def test_update_legal_brief_rollback_on_error(
    session, client, user_admin, token_admin
):
    brief = LegalBrief(
        title='Teste rollback', content='Conteúdo', created_by_id=user_admin.id
    )
    session.add(brief)
    await session.commit()
    await session.refresh(brief)

    bad_data = {'title': None, 'content': None}

    response = client.put(
        ENDPOINT_URL + f'/{brief.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
        json=bad_data,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    response = client.get(
        ENDPOINT_URL + f'/{brief.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    revisions = response.json()['revisions']
    assert len(revisions) == 0


@pytest.mark.asyncio
async def test_update_canceled_brief_rejected(
    session, client, user_admin, token_admin
):
    """Exemplo opcional: atualização bloqueada se canceled=True"""
    brief = LegalBrief(
        title='Cancelado',
        content='Antigo',
        created_by_id=user_admin.id,
        canceled=True,
        canceled_by_id=user_admin.id,
        canceled_at=datetime.now(),
    )
    session.add(brief)
    await session.commit()
    await session.refresh(brief)

    response = client.put(
        ENDPOINT_URL + f'/{brief.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
        json={
            'title': 'Tentativa de atualização',
            'content': 'Tentativa de atualização',
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (
        response.json()['detail']
        == 'This Legal Brief has already been canceled.'
    )


@pytest.mark.asyncio
async def test_cancel_legal_brief_success(
    client, session, user_admin, token_admin
):
    legal_brief = LegalBriefFactory(created_by_id=user_admin.id)

    session.add(legal_brief)
    await session.commit()
    await session.refresh(legal_brief)

    response = client.patch(
        ENDPOINT_URL + f'/{legal_brief.id}/cancel',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['canceled'] is True
    assert data['canceled_by']['id'] == user_admin.id
    assert data['canceled_at'] is not None


def test_cancel_legal_brief_not_found(client, token_admin):
    response = client.patch(
        ENDPOINT_URL + '/99999/cancel',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_cancel_legal_brief_already_canceled(
    client, session, user_admin, token_admin
):
    legal_brief = LegalBriefFactory(created_by_id=user_admin.id, canceled=True)
    session.add(legal_brief)
    await session.commit()
    await session.refresh(legal_brief)

    response = client.patch(
        ENDPOINT_URL + f'/{legal_brief.id}/cancel',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'already' in response.json()['detail'].lower()
