from http import HTTPStatus

ENDPOINT_URL = '/api/v1/notices'


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
