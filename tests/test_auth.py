from http import HTTPStatus

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
