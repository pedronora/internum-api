from http import HTTPStatus

from sqlalchemy.exc import OperationalError

from internum.app import app, create_app
from internum.core.database import get_session


class _BrokenSession:
    @staticmethod
    async def execute(*args, **kwargs):
        raise OperationalError('SELECT 1', {}, Exception('detalhe interno'))


def test_status_deve_retornar_ok(client):
    response = client.get('/api/v1/status')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'status': 'ok'}


def test_status_nao_expoe_detalhes_do_banco(client):
    app.dependency_overrides[get_session] = _BrokenSession

    try:
        response = client.get('/api/v1/status')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {'detail': 'Serviço indisponível'}
    assert 'detalhe interno' not in response.text


def test_docs_seguem_a_flag_de_configuracao():
    app_com_docs = create_app(docs_enabled=True)
    app_sem_docs = create_app(docs_enabled=False)

    assert app_com_docs.docs_url == '/docs'
    assert app_com_docs.redoc_url == '/redoc'
    assert app_com_docs.openapi_url == '/openapi.json'
    assert app_sem_docs.docs_url is None
    assert app_sem_docs.redoc_url is None
    assert app_sem_docs.openapi_url is None
