from http import HTTPStatus

from internum.modules.users.models import User
from internum.modules.users.schemas import UserRead

ENDPOINT_URL = '/api/v1/users'


def test_create_user(client, mock_db_time, token_admin):
    with mock_db_time(model=User) as time:
        response = client.post(
            ENDPOINT_URL,
            headers={'Authorization': f'Bearer {token_admin}'},
            json={
                'name': 'Pedro Nora',
                'username': 'User_1',
                'password': '@1Senha-teste',
                'email': 'TEST@test.com',
                'birthday': '2020-01-01',
                'role': 'user',
                'setor': 'oficial',
                'subsetor': 'titular',
            },
        )

    data = response.json()

    assert response.status_code == HTTPStatus.CREATED
    assert isinstance(data['id'], int)
    assert data['id'] > 0
    assert data['name'] == 'Pedro Nora'
    assert data['username'] == 'User_1'
    assert data['email'] == 'test@test.com'
    assert data['birthday'] == '2020-01-01'
    assert data['created_at'] == time.isoformat() + 'Z'


def test_create_user_without_permission(client, mock_db_time, token):
    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token}'},
        json={
            'name': 'Pedro Nora',
            'username': 'User_1',
            'password': 'senha-teste',
            'email': 'test@test.com',
            'birthday': '2020-01-01',
            'role': 'user',
            'setor': 'oficial',
            'subsetor': 'titular',
        },
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Acesso negado: usuário sem permissão'


def test_create_user_with_existent_username(client, user, token_admin):
    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
        json={
            'name': user.name,
            'username': user.username,
            'password': user.clean_password,
            'email': 'other@mail.com',
            'birthday': '2020-01-01',
            'setor': user.setor,
            'subsetor': user.subsetor,
            'role': user.role,
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail'] == 'Usuário já existente.'


def test_create_user_with_existent_email(client, user, token_admin):
    response = client.post(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
        json={
            'name': user.name,
            'username': 'new_username',
            'password': user.clean_password,
            'email': user.email,
            'birthday': '2020-01-01',
            'setor': user.setor,
            'subsetor': user.subsetor,
            'role': user.role,
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail'] == 'Email já existente.'


def test_get_users(client, token_admin):
    response = client.get(
        ENDPOINT_URL, headers={'Authorization': f'Bearer {token_admin}'}
    )

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()['users']) > 0


def test_get_users_without_permissions(client, token):
    response = client.get(
        ENDPOINT_URL, headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Acesso negado: usuário sem permissão'


def test_get_user(client, user, token):
    expected_data = UserRead.model_validate(user).model_dump(mode='json')

    response = client.get(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK

    assert response.json() == expected_data


def test_get_user_by_id_not_found(client, token_admin):
    response = client.get(
        f'{ENDPOINT_URL}/999999',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert (
        response.json()['detail'] == 'Não encontrado usuário com id (999999).'
    )


def test_get_user_by_id_inactive(client, user_inactive, token_admin):
    response = client.get(
        f'{ENDPOINT_URL}/{user_inactive.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert (
        response.json()['detail']
        == f'Não encontrado usuário com id ({user_inactive.id}).'
    )


def test_update_user_success(client, user, token):
    update_data = {
        'name': 'Novo Nome',
        'email': 'novo.email@test.com',
    }

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.OK
    resp_json = response.json()
    assert resp_json['name'] == 'Novo Nome'
    assert resp_json['email'] == 'novo.email@test.com'
    assert resp_json['username'] == user.username


def test_update_email_upper_char(client, user, token):
    update_data = {
        'email': 'NOVO.email@test.com',
    }

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['email'] == 'novo.email@test.com'


def test_update_user_partial_data(client, user, token):
    update_data = {'name': 'Nome Parcial'}

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['name'] == 'Nome Parcial'
    assert response.json()['email'] == user.email
    assert response.json()['username'] == user.username


def test_update_user_restricted_fields_forbidden(client, user, token):
    update_data = {
        'subsetor': 'Novo Subsetor',
        'role': 'admin',
        'active': False,
    }

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert 'Acesso negado' in response.json()['detail']


def test_update_user_all_fields(client, user, token_admin):
    update_data = {
        'name': 'Nome Completo',
        'username': 'novousername',
        'email': 'novo@email.com',
        'setor': 'administrativo',
        'subsetor': 'Desenvolvimento',
        'role': 'admin',
        'active': False,
    }

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['name'] == 'Nome Completo'
    assert data['username'] == 'novousername'
    assert data['email'] == 'novo@email.com'
    assert data['setor'] == 'administrativo'
    assert data['subsetor'] == 'Desenvolvimento'
    assert data['role'] == 'admin'
    assert not data['active']


def test_update_role_without_permissions(client, user, token):
    update_data = {'role': 'coord'}

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == (
        'Acesso negado: usuário sem permissão para definir os '
        'campos perfil, setor, subsetor e ativo'
    )


def test_update_user_empty_payload(client, user, token):
    original_name = user.name
    original_email = user.email

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['name'] == original_name
    assert data['email'] == original_email


def test_update_user_with_none_values(client, user, token):
    original_name = user.name
    update_data = {'name': None, 'email': 'outro@email.com'}

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['name'] == original_name
    assert response.json()['email'] == 'outro@email.com'


def test_update_user_not_found(client, token_admin):
    update_data = {'name': 'Novo Nome'}

    response = client.put(
        f'{ENDPOINT_URL}/9999',
        headers={'Authorization': f'Bearer {token_admin}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'Não encontrado' in response.json()['detail']


def test_update_user_inactive(client, user_inactive, token):
    update_data = {'name': 'Novo Nome'}
    response = client.put(
        f'/users/{user_inactive.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_user_duplicate_username(
    client, session, user, other_user, token
):
    update_data = {'username': other_user.username}
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert (
        'Username' in response.json()['detail']
        or 'existem' in response.json()['detail']
    )


def test_update_user_duplicate_email(client, session, user, other_user, token):
    update_data = {'email': other_user.email}
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert (
        'Email' in response.json()['detail']
        or 'existem' in response.json()['detail']
    )


def test_update_user_invalid_data(client, user, token):
    update_data = {
        'email': 'email-invalido',
        'name': '',
    }

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_user_same_data(client, user, token):
    update_data = {
        'name': user.name,
        'email': user.email,
    }

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )
    assert response.status_code == HTTPStatus.OK


def test_update_user_case_sensitivity_email(client, user, token):
    update_data = {'email': user.email.upper()}

    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json=update_data,
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['email'] == user.email.upper().lower()


def test_deactivate_user_success(client, user, token_admin):
    response = client.delete(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b''


def test_deactivate_user_without_permission(client, user, token):
    response = client.delete(
        f'{ENDPOINT_URL}/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Acesso negado: usuário sem permissão'


def test_deactivate_user_not_found(client, token_admin):
    response = client.delete(
        f'{ENDPOINT_URL}/9999',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'Não encontrado usuário com id (9999).' == response.json()['detail']


def test_deactivate_user_already_inactive(client, user_inactive, token_admin):
    response = client.delete(
        f'{ENDPOINT_URL}/{user_inactive.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (
        f'Usuário com id ({user_inactive.id}) já está inativo.'
        == response.json()['detail']
    )


def test_user_change_pwd(client, user, token):
    data = {'old_password': user.clean_password, 'new_password': '@Aa12345678'}

    response = client.post(
        f'{ENDPOINT_URL}/{user.id}/change-password',
        headers={'Authorization': f'Bearer {token}'},
        json=data,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['message'] == 'Senha alterada com sucesso'


def test_user_change_with_same_pwd(client, user, token):
    data = {
        'old_password': user.clean_password,
        'new_password': user.clean_password,
    }
    response = client.post(
        f'{ENDPOINT_URL}/{user.id}/change-password',
        headers={'Authorization': f'Bearer {token}'},
        json=data,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == 'Senha nova igual à atual.'


def test_change_pwd_user_not_found(client, token_admin):
    data = {
        'old_password': '@Aa12345678',
        'new_password': '@Aa12345678@',
    }
    response = client.post(
        f'{ENDPOINT_URL}/9999/change-password',
        headers={'Authorization': f'Bearer {token_admin}'},
        json=data,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail'] == 'Não encontrado usuário com id (9999).'


def test_change_pwd_without_permission(client, user, other_user, token):
    response = client.post(
        f'{ENDPOINT_URL}/{other_user.id}/change-password',
        headers={'Authorization': f'Bearer {token}'},
        json={'password': user.clean_password},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Acesso negado: usuário sem permissão'
