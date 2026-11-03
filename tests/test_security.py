from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from jwt import decode, encode

from internum.core.security import create_access_token, create_refresh_token
from internum.core.settings import Settings

settings = Settings()

ENDPOINT_URL = '/api/v1'


def test_jwt():
    data = {'teste': 'teste'}
    token = create_access_token(data)

    decoded = decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )

    assert decoded['teste'] == data['teste']
    assert decoded['type'] == 'access'
    assert 'exp' in decoded
    assert 'iat' in decoded


def test_jwt_invalid_token(client):
    response = client.delete(
        f'{ENDPOINT_URL}/users/1',
        headers={'Authorization': 'Bearer token-invalido'},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        'detail': 'Não foi possível validar as credenciais'
    }


def test_refresh_token_nao_autentica_como_access(client, user):
    token = create_refresh_token(data={'sub': user.username})

    response = client.get(
        f'{ENDPOINT_URL}/users/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_token_sem_iat_e_rejeitado(client, user):
    token = encode(
        {
            'sub': user.username,
            'exp': datetime.now(UTC) + timedelta(minutes=5),
            'type': 'access',
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    response = client.get(
        f'{ENDPOINT_URL}/users/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_token_de_reset_nao_autentica_como_access(client, user, token_factory):
    token = token_factory(user.id)

    response = client.get(
        f'{ENDPOINT_URL}/users/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
