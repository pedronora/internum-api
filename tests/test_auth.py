from http import HTTPStatus

from freezegun import freeze_time

ENDPOINT_URL = '/api/v1/auth'


def test_get_token(client, user):
    response = client.post(
        ENDPOINT_URL + '/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    token = response.json()

    assert response.status_code == HTTPStatus.OK
    assert 'access_token' in token
    assert 'token_type' in token


def test_token_expired_after_time(client, user):
    with freeze_time('2025-09-17 12:00:00'):
        response = client.post(
            f'{ENDPOINT_URL}/token',
            data={'username': user.username, 'password': user.clean_password},
        )
        assert response.status_code == HTTPStatus.OK
        token = response.json()['access_token']

    with freeze_time('2025-09-17 12:31:00'):
        response = client.put(
            f'{ENDPOINT_URL[:-5]}/users/{user.id}',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'username': 'wrongwrong',
                'email': 'wrong@wrong.com',
                'password': 'wrong',
            },
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json() == {
            'detail': 'Não foi possível validar as credenciais'
        }


def test_token_inexistent_user(client):
    response = client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': 'no_user@no_domain.com', 'password': 'testtest'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Email ou senha incorretos'}


def test_token_wrong_password(client, user):
    response = client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': 'wrong_password'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Email ou senha incorretos'}


def test_token_expired_dont_refresh(client, user):
    with freeze_time('2025-09-18 12:00:00'):
        response = client.post(
            f'{ENDPOINT_URL}/token',
            data={'username': user.username, 'password': user.clean_password},
        )
        assert response.status_code == HTTPStatus.OK
        token = response.json()['access_token']

    with freeze_time('2025-09-18 12:31:00'):
        response = client.post(
            f'{ENDPOINT_URL}/refresh_token',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json() == {
            'detail': 'Não foi possível validar as credenciais'
        }
