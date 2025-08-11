from http import HTTPStatus

from fastapi.testclient import TestClient

from internum.app import app

client = TestClient(app)


def test_status_deve_retornar_ok():
    client = TestClient(app)

    response = client.get('/api/v1/status')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'ok'
