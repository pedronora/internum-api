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


def test_update_user_success(client, user):
    """Testa atualização bem-sucedida de usuário"""
    update_data = {
        'name': 'Novo Nome',
        'email': 'novo.email@test.com',
        'subsetor': 'Novo Subsetor',
    }

    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)

    assert response.status_code == HTTPStatus.OK
    assert response.json()['name'] == 'Novo Nome'
    assert response.json()['email'] == 'novo.email@test.com'
    assert response.json()['subsetor'] == 'Novo Subsetor'
    assert response.json()['username'] == user.username


def test_update_user_partial_data(client, user):
    """Testa atualização parcial com apenas alguns campos"""
    update_data = {'name': 'Nome Parcial'}

    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)

    assert response.status_code == HTTPStatus.OK
    assert response.json()['name'] == 'Nome Parcial'
    assert response.json()['email'] == user.email
    assert response.json()['username'] == user.username


def test_update_user_all_fields(client, user):
    """Testa atualização de todos os campos permitidos"""
    update_data = {
        'name': 'Nome Completo',
        'username': 'novousername',
        'email': 'novo@email.com',
        'setor': 'administrativo',
        'subsetor': 'Desenvolvimento',
        'role': 'admin',
        'active': False,
    }

    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['name'] == 'Nome Completo'
    assert data['username'] == 'novousername'
    assert data['email'] == 'novo@email.com'
    assert data['setor'] == 'administrativo'
    assert data['subsetor'] == 'Desenvolvimento'
    assert data['role'] == 'admin'
    assert not data['active']


def test_update_user_empty_payload(client, user):
    original_name = user.name
    original_email = user.email

    response = client.put(f'{ENDPOINT_URL}/{user.id}', json={})

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['name'] == original_name
    assert data['email'] == original_email


def test_update_user_with_none_values(client, user):
    """Testa comportamento ao enviar valores None (deve ignorar)"""
    original_name = user.name
    update_data = {'name': None, 'email': 'outro@email.com'}

    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)

    assert response.status_code == HTTPStatus.OK
    assert response.json()['name'] == original_name
    assert response.json()['email'] == 'outro@email.com'


def test_update_user_not_found(client):
    update_data = {'name': 'Novo Nome'}

    response = client.put(f'{ENDPOINT_URL}/9999', json=update_data)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'Não encontrado' in response.json()['detail']


def test_update_user_inactive(client, user_inactive):
    update_data = {'name': 'Novo Nome'}
    response = client.put(f'/users/{user_inactive.id}', json=update_data)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_user_duplicate_username(client, session, user, another_user):
    update_data = {'username': another_user.username}
    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)

    assert response.status_code == HTTPStatus.CONFLICT
    assert (
        'Username' in response.json()['detail']
        or 'existem' in response.json()['detail']
    )


def test_update_user_duplicate_email(client, session, user, another_user):
    update_data = {'email': another_user.email}
    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)

    assert response.status_code == HTTPStatus.CONFLICT
    assert (
        'Email' in response.json()['detail']
        or 'existem' in response.json()['detail']
    )


def test_update_user_invalid_data(client, user):
    """Testa validação de dados inválidos"""
    update_data = {
        'email': 'email-invalido',
        'name': '',
    }

    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_user_same_data(client, user):
    update_data = {
        'name': user.name,
        'email': user.email,
    }

    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)
    assert response.status_code == HTTPStatus.OK


def test_update_user_case_sensitivity_email(client, user):
    update_data = {'email': user.email.upper()}

    response = client.put(f'{ENDPOINT_URL}/{user.id}', json=update_data)
    assert response.status_code == HTTPStatus.OK
    assert response.json()['email'] == user.email.upper().lower()


def test_deactivate_user_success(client, user):
    response = client.delete(f'{ENDPOINT_URL}/{user.id}')

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b''


def test_deactivate_user_not_found(client):
    response = client.delete(f'{ENDPOINT_URL}/9999')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'Não encontrado usuário com id (9999).' == response.json()['detail']


def test_deactivate_user_already_inactive(client, user_inactive):
    response = client.delete(f'{ENDPOINT_URL}/{user_inactive.id}')

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (
        f'Usuário com id ({user_inactive.id}) já está inativo.'
        == response.json()['detail']
    )
