from http import HTTPStatus
from uuid import uuid4

from freezegun import freeze_time

from internum.core.settings import Settings
from internum.modules.users.enums import Role
from internum.modules.users.models import User
from internum.modules.users.schemas import UserRead

ENDPOINT_URL = '/api/v1/users'
GROSS_SALARY = 5200.50
settings = Settings()


def build_test_password() -> str:
    return f'Aa1!{uuid4().hex[:8]}'


def build_payload(**overrides) -> dict:
    payload = {
        'name': 'Pedro Nora',
        'username': 'User_1',
        'password': build_test_password(),
        'cpf': '123.456.789-09',
        'email': 'TEST@test.com',
        'birthday': '2020-01-01',
        'hiring_date': '2026-02-05',
        'unidade': 'registro',
        'subunidade': 'Análise',
        'roles': ['colaborador_registro'],
    }
    payload.update(overrides)
    return payload


def auth(token: str) -> dict:
    return {'Authorization': f'Bearer {token}'}


def refresh_with(client, refresh_token: str):
    client.cookies.clear()
    return client.post(
        '/api/v1/auth/refresh_token',
        headers={'Cookie': f'{settings.REFRESH_COOKIE_NAME}={refresh_token}'},
    )


def test_create_user(client, mock_db_time, token_admin):
    with mock_db_time(model=User) as time:
        response = client.post(
            ENDPOINT_URL,
            headers=auth(token_admin),
            json=build_payload(
                phone='(45) 99999-9999',
                gross_salary=GROSS_SALARY,
            ),
        )

    data = response.json()

    assert response.status_code == HTTPStatus.CREATED
    assert isinstance(data['id'], int)
    assert data['id'] > 0
    assert data['name'] == 'Pedro Nora'
    assert data['username'] == 'User_1'
    assert data['cpf'] == '12345678909'
    assert data['email'] == 'test@test.com'
    assert data['birthday'] == '2020-01-01'
    assert data['unidade'] == 'registro'
    assert data['subunidade'] == 'Análise'
    assert data['roles'] == ['colaborador_registro']
    assert data['phone'] == '45999999999'
    assert data['gross_salary'] is not None
    assert float(data['gross_salary']) == GROSS_SALARY
    assert data['created_at'] == time.isoformat() + 'Z'


def test_create_user_without_permission(client, token):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token),
        json=build_payload(),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Acesso negado: usuário sem permissão'


def test_create_user_without_cpf(client, token_admin):
    payload = build_payload()
    payload.pop('cpf')

    response = client.post(
        ENDPOINT_URL, headers=auth(token_admin), json=payload
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_user_with_invalid_cpf(client, token_admin):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_admin),
        json=build_payload(cpf='11111111111'),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_user_with_invalid_phone(client, token_admin):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_admin),
        json=build_payload(phone='(45) 123'),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_user_with_negative_gross_salary(client, token_admin):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_admin),
        json=build_payload(gross_salary=-1),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_user_with_existent_username(client, user, token_admin):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_admin),
        json=build_payload(
            name=user.name,
            username=user.username,
            email='other@mail.com',
            cpf='12345678909',
        ),
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail'] == 'Usuário já existente.'


def test_create_user_with_existent_email(client, user, token_admin):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_admin),
        json=build_payload(
            username='new_username',
            email=user.email,
            cpf='12345678909',
        ),
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail'] == 'Email já existente.'


def test_create_admin_by_coord(client, token_coord):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_coord),
        json=build_payload(roles=['admin']),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == (
        'Acesso negado: você não pode atribuir este perfil.'
    )


def test_create_user_by_coord(client, token_coord):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_coord),
        json=build_payload(email='coord-created@test.com'),
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['roles'] == ['colaborador_registro']


def test_create_gestao_coord_by_coord_gestao(client, token_coord_gestao):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_coord_gestao),
        json=build_payload(roles=['coord_gestao']),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == (
        'Acesso negado: você não pode atribuir este perfil.'
    )


def test_create_non_admin_role_by_oficial(client, token_oficial):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_oficial),
        json=build_payload(roles=['suboficial']),
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['roles'] == ['suboficial']


def test_create_with_salary_by_coord_forbidden(client, token_coord):
    response = client.post(
        ENDPOINT_URL,
        headers=auth(token_coord),
        json=build_payload(gross_salary=5000),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == (
        'Acesso negado: sem permissão para definir salário.'
    )


def test_get_users(client, token_admin):
    response = client.get(ENDPOINT_URL, headers=auth(token_admin))

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()['users']) > 0
    assert 'cpf' in response.json()['users'][0]
    assert 'gross_salary' in response.json()['users'][0]


def test_get_users_without_permissions(client, token):
    response = client.get(ENDPOINT_URL, headers=auth(token))

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Acesso negado: usuário sem permissão'


def test_get_user_directory(client, user, token):
    response = client.get(ENDPOINT_URL + '/directory', headers=auth(token))

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    directory_user = next(
        item for item in data['users'] if item['id'] == user.id
    )
    assert directory_user['name'] == user.name
    assert directory_user['roles'] == ['colaborador_registro']
    assert 'cpf' not in directory_user
    assert 'gross_salary' not in directory_user
    assert 'birthday' not in directory_user


def test_get_user(client, user, token):
    expected_data = UserRead.model_validate(user).model_dump(mode='json')

    response = client.get(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == expected_data
    assert 'termination_date' in response.json()


def test_get_other_user_without_sensitive_permission(
    client, user, other_user, token
):
    response = client.get(
        f'{ENDPOINT_URL}/{other_user.id}',
        headers=auth(token),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_get_other_user_as_coord(client, user, other_user, token_coord):
    response = client.get(
        f'{ENDPOINT_URL}/{other_user.id}',
        headers=auth(token_coord),
    )

    assert response.status_code == HTTPStatus.OK


def test_get_user_by_id_not_found(client, token_admin):
    response = client.get(
        f'{ENDPOINT_URL}/999999',
        headers=auth(token_admin),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert (
        response.json()['detail'] == 'Não encontrado usuário com id (999999).'
    )


def test_get_user_by_id_inactive(client, user_inactive, token_admin):
    response = client.get(
        f'{ENDPOINT_URL}/{user_inactive.id}',
        headers=auth(token_admin),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert (
        response.json()['detail']
        == f'Não encontrado usuário com id ({user_inactive.id}).'
    )


def test_get_me_includes_roles_and_permissions(client, token):
    response = client.get(ENDPOINT_URL + '/me', headers=auth(token))

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['roles'] == ['colaborador_registro']
    assert 'users:read' in data['permissions']
    assert 'users:read_sensitive' not in data['permissions']


def test_update_user_success(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={
            'name': 'Novo Nome',
            'email': 'novo.email@test.com',
        },
    )

    assert response.status_code == HTTPStatus.OK
    resp_json = response.json()
    assert resp_json['name'] == 'Novo Nome'
    assert resp_json['email'] == 'novo.email@test.com'
    assert resp_json['username'] == user.username


def test_update_email_upper_char(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'email': 'NOVO.email@test.com'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['email'] == 'novo.email@test.com'


def test_update_user_partial_data(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'name': 'Nome Parcial'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['name'] == 'Nome Parcial'
    assert response.json()['email'] == user.email
    assert response.json()['username'] == user.username


def test_update_user_restricted_fields_forbidden(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={
            'subunidade': 'Outra',
            'roles': ['admin'],
            'active': False,
        },
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert 'Acesso negado' in response.json()['detail']


def test_update_own_salary_forbidden(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'gross_salary': 5000.00},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert 'Acesso negado' in response.json()['detail']


def test_update_own_roles_forbidden(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'roles': ['admin']},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == (
        'Acesso negado: você não pode alterar seus perfis.'
    )


def test_update_gross_salary_by_admin(client, user, token_admin):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token_admin),
        json={'gross_salary': GROSS_SALARY},
    )

    assert response.status_code == HTTPStatus.OK
    assert float(response.json()['gross_salary']) == GROSS_SALARY


def test_update_gross_salary_by_coord_forbidden(client, user, token_coord):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token_coord),
        json={'gross_salary': 5200.50},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_update_phone_by_self(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'phone': '(45) 99999-9999'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['phone'] == '45999999999'


def test_update_phone_invalid(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'phone': '123'},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_user_all_fields(client, user, token_admin):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token_admin),
        json={
            'name': 'Nome Completo',
            'username': 'novousername',
            'cpf': '529.982.247-25',
            'email': 'novo@email.com',
            'hiring_date': '2026-01-01',
            'termination_date': '2026-02-01',
            'unidade': 'gestao',
            'subunidade': 'Desenvolvimento',
            'roles': ['admin'],
            'active': False,
        },
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['name'] == 'Nome Completo'
    assert data['username'] == 'novousername'
    assert data['cpf'] == '52998224725'
    assert data['email'] == 'novo@email.com'
    assert data['hiring_date'] == '2026-01-01'
    assert data['termination_date'] == '2026-02-01'
    assert data['unidade'] == 'gestao'
    assert data['subunidade'] == 'Desenvolvimento'
    assert data['roles'] == ['admin']
    assert not data['active']


def test_update_user_reject_termination_date_when_active(
    client, user, token_admin
):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token_admin),
        json={
            'active': True,
            'termination_date': '2026-02-01',
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_role_to_admin_by_coord(client, user, token_coord):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token_coord),
        json={'roles': ['admin']},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == (
        'Acesso negado: você não pode atribuir este perfil.'
    )


def test_update_user_empty_payload(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['name'] == user.name
    assert data['email'] == user.email


def test_update_user_with_none_values(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'name': None, 'email': 'outro@email.com'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['name'] == user.name
    assert response.json()['email'] == 'outro@email.com'


def test_update_user_not_found(client, token_admin):
    response = client.put(
        f'{ENDPOINT_URL}/9999',
        headers=auth(token_admin),
        json={'name': 'Novo Nome'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'Não encontrado' in response.json()['detail']


def test_update_user_inactive(client, user_inactive, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user_inactive.id}',
        headers=auth(token),
        json={'name': 'Novo Nome'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_user_duplicate_username(client, user, other_user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'username': other_user.username},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert (
        'Username' in response.json()['detail']
        or 'existem' in response.json()['detail']
    )


def test_update_user_duplicate_email(client, user, other_user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'email': other_user.email},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert (
        'Email' in response.json()['detail']
        or 'existem' in response.json()['detail']
    )


def test_update_user_duplicate_cpf(client, user, other_user, token_admin):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token_admin),
        json={'cpf': other_user.cpf},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert (
        'CPF' in response.json()['detail']
        or 'existem' in response.json()['detail']
    )


def test_update_user_invalid_data(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={
            'email': 'email-invalido',
            'name': '',
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_user_same_data(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={
            'name': user.name,
            'email': user.email,
        },
    )

    assert response.status_code == HTTPStatus.OK


def test_update_user_case_sensitivity_email(client, user, token):
    response = client.put(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
        json={'email': user.email.upper()},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['email'] == user.email.upper().lower()


def test_deactivate_user_success(client, user, token_admin):
    response = client.delete(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token_admin),
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b''


def test_deactivate_user_without_permission(client, user, token):
    response = client.delete(
        f'{ENDPOINT_URL}/{user.id}',
        headers=auth(token),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Acesso negado: usuário sem permissão'


def test_deactivate_user_not_found(client, token_admin):
    response = client.delete(
        f'{ENDPOINT_URL}/9999',
        headers=auth(token_admin),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert 'Não encontrado usuário com id (9999).' == response.json()['detail']


def test_deactivate_user_already_inactive(client, user_inactive, token_admin):
    response = client.delete(
        f'{ENDPOINT_URL}/{user_inactive.id}',
        headers=auth(token_admin),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert (
        f'Usuário com id ({user_inactive.id}) já está inativo.'
        == response.json()['detail']
    )


def test_deactivate_self_forbidden(client, user_coord, token_coord):
    response = client.delete(
        f'{ENDPOINT_URL}/{user_coord.id}',
        headers=auth(token_coord),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_deactivate_last_admin_forbidden(client, user_admin, token_oficial):
    response = client.delete(
        f'{ENDPOINT_URL}/{user_admin.id}',
        headers=auth(token_oficial),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == (
        'Não é possível remover o último administrador ativo.'
    )


def test_user_change_pwd(client, user, token):
    response = client.post(
        f'{ENDPOINT_URL}/{user.id}/change-password',
        headers=auth(token),
        json={
            'old_password': user.clean_password,
            'new_password': build_test_password(),
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['message'] == 'Senha alterada com sucesso'


def test_user_change_with_same_pwd(client, user, token):
    response = client.post(
        f'{ENDPOINT_URL}/{user.id}/change-password',
        headers=auth(token),
        json={
            'old_password': user.clean_password,
            'new_password': user.clean_password,
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == 'Senha nova igual à atual.'


def test_change_pwd_user_not_found(client, token_admin):
    response = client.post(
        f'{ENDPOINT_URL}/9999/change-password',
        headers=auth(token_admin),
        json={
            'old_password': build_test_password(),
            'new_password': build_test_password(),
        },
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail'] == 'Não encontrado usuário com id (9999).'


def test_change_pwd_without_permission(client, user, other_user, token):
    response = client.post(
        f'{ENDPOINT_URL}/{other_user.id}/change-password',
        headers=auth(token),
        json={
            'old_password': user.clean_password,
            'new_password': build_test_password(),
        },
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail'] == 'Acesso negado: usuário sem permissão'


def test_admin_change_other_user_password(client, other_user, token_admin):
    response = client.post(
        f'{ENDPOINT_URL}/{other_user.id}/change-password',
        headers=auth(token_admin),
        json={
            'old_password': other_user.clean_password,
            'new_password': build_test_password(),
        },
    )

    assert response.status_code == HTTPStatus.OK


def test_change_pwd_retorna_novo_access_token(client, user, token):
    response = client.post(
        f'{ENDPOINT_URL}/{user.id}/change-password',
        headers=auth(token),
        json={
            'old_password': user.clean_password,
            'new_password': build_test_password(),
        },
    )

    assert response.status_code == HTTPStatus.OK
    new_token = response.json()['access_token']

    assert (
        client.get(f'{ENDPOINT_URL}/me', headers=auth(new_token)).status_code
        == HTTPStatus.OK
    )


def test_change_pwd_invalida_access_token_anterior(client, user):
    with freeze_time('2025-09-17 12:00:00') as frozen:
        login = client.post(
            '/api/v1/auth/token',
            data={
                'username': user.username,
                'password': user.clean_password,
            },
        )
        old_token = login.json()['access_token']

        frozen.move_to('2025-09-17 12:00:05.500000')

        response = client.post(
            f'{ENDPOINT_URL}/{user.id}/change-password',
            headers=auth(old_token),
            json={
                'old_password': user.clean_password,
                'new_password': build_test_password(),
            },
        )
        assert response.status_code == HTTPStatus.OK
        new_token = response.json()['access_token']

        assert (
            client.get(
                f'{ENDPOINT_URL}/me', headers=auth(new_token)
            ).status_code
            == HTTPStatus.OK
        )
        assert (
            client.get(
                f'{ENDPOINT_URL}/me', headers=auth(old_token)
            ).status_code
            == HTTPStatus.UNAUTHORIZED
        )


def test_change_pwd_mantem_refresh_da_sessao_atual(client, user, token):
    refresh_token = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    response = client.post(
        f'{ENDPOINT_URL}/{user.id}/change-password',
        headers=auth(token),
        json={
            'old_password': user.clean_password,
            'new_password': build_test_password(),
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert refresh_with(client, refresh_token).status_code == HTTPStatus.OK


def test_change_pwd_revoga_outras_sessoes(client, user):
    credentials = {
        'username': user.username,
        'password': user.clean_password,
    }

    with freeze_time('2025-09-17 12:00:00') as frozen:
        first = client.post('/api/v1/auth/token', data=credentials)
        first_access = first.json()['access_token']
        first_refresh = client.cookies.get(settings.REFRESH_COOKIE_NAME)

        second = client.post('/api/v1/auth/token', data=credentials)
        second_access = second.json()['access_token']
        second_refresh = client.cookies.get(settings.REFRESH_COOKIE_NAME)

        frozen.move_to('2025-09-17 12:00:05')

        response = client.post(
            f'{ENDPOINT_URL}/{user.id}/change-password',
            headers=auth(second_access),
            json={
                'old_password': user.clean_password,
                'new_password': build_test_password(),
            },
        )
        assert response.status_code == HTTPStatus.OK

        assert (
            refresh_with(client, first_refresh).status_code
            == HTTPStatus.UNAUTHORIZED
        )
        assert (
            refresh_with(client, second_refresh).status_code == HTTPStatus.OK
        )
        assert (
            client.get(
                f'{ENDPOINT_URL}/me', headers=auth(first_access)
            ).status_code
            == HTTPStatus.UNAUTHORIZED
        )


def test_admin_change_pwd_revoga_sessoes_do_alvo(
    client, user_admin, other_user
):
    with freeze_time('2025-09-17 12:00:00') as frozen:
        admin_login = client.post(
            '/api/v1/auth/token',
            data={
                'username': user_admin.username,
                'password': user_admin.clean_password,
            },
        )
        admin_access = admin_login.json()['access_token']
        admin_refresh = client.cookies.get(settings.REFRESH_COOKIE_NAME)

        target_login = client.post(
            '/api/v1/auth/token',
            data={
                'username': other_user.username,
                'password': other_user.clean_password,
            },
        )
        target_access = target_login.json()['access_token']
        target_refresh = client.cookies.get(settings.REFRESH_COOKIE_NAME)

        frozen.move_to('2025-09-17 12:00:05')

        response = client.post(
            f'{ENDPOINT_URL}/{other_user.id}/change-password',
            headers=auth(admin_access),
            json={
                'old_password': other_user.clean_password,
                'new_password': build_test_password(),
            },
        )
        assert response.status_code == HTTPStatus.OK

        assert (
            refresh_with(client, target_refresh).status_code
            == HTTPStatus.UNAUTHORIZED
        )
        assert refresh_with(client, admin_refresh).status_code == HTTPStatus.OK
        assert (
            client.get(
                f'{ENDPOINT_URL}/me', headers=auth(target_access)
            ).status_code
            == HTTPStatus.UNAUTHORIZED
        )


def test_role_is_job_not_permission_source(client, user, token):
    response = client.get(ENDPOINT_URL + '/me', headers=auth(token))

    assert response.status_code == HTTPStatus.OK
    assert response.json()['roles'] == [Role.COLABORADOR_REGISTRO.value]
