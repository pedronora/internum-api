from http import HTTPStatus

from jwt import decode

from internum.core.security import create_access_token
from internum.core.settings import Settings

settings = Settings()


def test_jwt():
    data = {'teste': 'teste'}
    token = create_access_token(data)

    decoded = decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )

    assert decoded['teste'] == data['teste']
    assert 'exp' in decoded


def test_jwt_invalid_token(client):
    response = client.delete(
        '/api/v1/users/1', headers={'Authorization': 'Bearer token-invalido'}
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}
