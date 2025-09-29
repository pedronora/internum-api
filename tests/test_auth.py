from http import HTTPStatus

from freezegun import freeze_time

from internum.core.settings import Settings

settings = Settings()

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


def test_token_expired_refresh_token(client, user):
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
        )
        assert response.status_code == HTTPStatus.OK
        assert 'access_token' in response.json().keys()
        assert response.json()['access_token'] != token


def test_token_expired_without_refresh_token(client, user):
    with freeze_time('2025-09-18 12:00:00'):
        response = client.post(
            f'{ENDPOINT_URL}/token',
            data={'username': user.username, 'password': user.clean_password},
        )
        assert response.status_code == HTTPStatus.OK

        client.cookies.clear()

    with freeze_time('2025-09-18 12:31:00'):
        response = client.post(
            f'{ENDPOINT_URL}/refresh_token',
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_successful_logout(client, user):
    login_response = client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    assert login_response.status_code == HTTPStatus.OK

    assert settings.REFRESH_COOKIE_NAME in client.cookies

    response = client.post(f'{ENDPOINT_URL}/logout')

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert settings.REFRESH_COOKIE_NAME not in client.cookies
