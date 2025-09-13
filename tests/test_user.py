from http import HTTPStatus

from internum.modules.users.models import User
from internum.modules.users.schemas import UserRead

ENDPOINT_URL = '/api/v1/users'


def test_create_user(client, mock_db_time):
    with mock_db_time(model=User) as time:
        response = client.post(
            ENDPOINT_URL,
            json={
                'name': 'Pedro Nora',
                'username': 'User_1',
                'password': 'senha-teste',
                'email': 'test@test.com',
                'role': 'user',
                'setor': 'oficial',
                'subsetor': 'titular',
            },
        )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json() == {
        'id': 1,
        'name': 'Pedro Nora',
        'username': 'User_1',
        'email': 'test@test.com',
        'role': 'user',
        'setor': 'oficial',
        'subsetor': 'titular',
        'active': True,
        'created_at': time.isoformat(),
        'updated_at': time.isoformat(),
    }


def test_get_user(client, user):
    expected_data = UserRead.model_validate(user).model_dump(mode='json')

    response = client.get(f'{ENDPOINT_URL}/{user.id}')

    assert response.status_code == HTTPStatus.OK

    assert response.json() == expected_data


def test_get_user_by_id_not_found(client):
    response = client.get(f'{ENDPOINT_URL}/999999')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert (
        response.json()['detail'] == 'Não encontrado usuário com id (999999).'
    )


def test_get_user_by_id_inactive(client, user):
    user.active = False

    response = client.get(f'{ENDPOINT_URL}/{user.id}')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert (
        response.json()['detail']
        == f'Não encontrado usuário com id ({user.id}).'
    )
