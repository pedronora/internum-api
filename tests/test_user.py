from http import HTTPStatus

from internum.modules.users.models import User

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
