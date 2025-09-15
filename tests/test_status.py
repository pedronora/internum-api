from http import HTTPStatus


def test_status_deve_retornar_ok(client):
    response = client.get('/api/v1/status')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'ok'
