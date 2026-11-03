from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from freezegun import freeze_time
from sqlalchemy import select

from internum.core.settings import Settings
from internum.modules.auth.models import PasswordResetToken, RefreshToken

settings = Settings()

ENDPOINT_URL = '/api/v1/auth'


def _refresh_with(client, refresh_token):
    return client.post(
        f'{ENDPOINT_URL}/refresh_token',
        headers={
            'Cookie': (f'{settings.REFRESH_COOKIE_NAME}={refresh_token}')
        },
    )


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


def test_get_token(client, user):
    response = client.post(
        ENDPOINT_URL + '/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    token = response.json()

    assert response.status_code == HTTPStatus.OK
    assert 'access_token' in token
    assert 'token_type' in token


def test_token_expired_after_time(client, user):
    with freeze_time('2025-09-17 12:00:00'):
        response = client.post(
            f'{ENDPOINT_URL}/token',
            data={'username': user.username, 'password': user.clean_password},
        )
        assert response.status_code == HTTPStatus.OK
        token = response.json()['access_token']

    with freeze_time('2025-09-17 12:31:00'):
        response = client.put(
            f'{ENDPOINT_URL[:-5]}/users/{user.id}',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'username': 'wrongwrong',
                'email': 'wrong@wrong.com',
                'password': 'wrong',
            },
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json() == {
            'detail': 'Não foi possível validar as credenciais'
        }


def test_token_inexistent_user(client):
    response = client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': 'no_user@no_domain.com', 'password': 'testtest'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Usuário ou senha incorretos'}


def test_token_wrong_password(client, user):
    response = client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': 'wrong_password'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Usuário ou senha incorretos'}


def test_token_expired_refresh_token(client, user):
    with freeze_time('2025-09-18 12:00:00'):
        response = client.post(
            f'{ENDPOINT_URL}/token',
            data={'username': user.username, 'password': user.clean_password},
        )
        assert response.status_code == HTTPStatus.OK
        token = response.json()['access_token']

    with freeze_time('2025-09-18 12:31:00'):
        response = client.post(
            f'{ENDPOINT_URL}/refresh_token',
        )
        assert response.status_code == HTTPStatus.OK
        assert 'access_token' in response.json().keys()
        assert response.json()['access_token'] != token


def test_token_expired_without_refresh_token(client, user):
    with freeze_time('2025-09-18 12:00:00'):
        response = client.post(
            f'{ENDPOINT_URL}/token',
            data={'username': user.username, 'password': user.clean_password},
        )
        assert response.status_code == HTTPStatus.OK

        client.cookies.clear()

    with freeze_time('2025-09-18 12:31:00'):
        response = client.post(
            f'{ENDPOINT_URL}/refresh_token',
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_refresh_token_missing(client):
    response = client.post(f'{ENDPOINT_URL}/refresh_token')
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Refresh token ausente'}


def test_successful_logout(client, user):
    login_response = client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    assert login_response.status_code == HTTPStatus.OK

    assert settings.REFRESH_COOKIE_NAME in client.cookies

    response = client.post(f'{ENDPOINT_URL}/logout')

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert settings.REFRESH_COOKIE_NAME not in client.cookies


def test_forgot_password_returns_ok_even_for_unknown_email(client):
    response = client.post(
        f'{ENDPOINT_URL}/forgot-password',
        json={'email': 'nao_existe@dominio.com'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        'message': 'Se o email existir, enviaremos '
        'instruções para redefinir a senha.'
    }


def test_forgot_password_sends_email_for_valid_user(
    mock_email_service, client, user
):
    response = client.post(
        f'{ENDPOINT_URL}/forgot-password',
        json={'email': user.email},
    )

    assert response.status_code == HTTPStatus.OK
    assert mock_email_service.call_count == 1


@pytest.mark.asyncio
async def test_reset_password_success(client, session, user, token_factory):
    token_reset = token_factory(user.id, purpose='password_reset')

    db_reset_token = PasswordResetToken(
        user_id=user.id,
        token=token_reset,
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        used=False,
    )

    session.add(db_reset_token)
    await session.commit()

    response = client.post(
        f'{ENDPOINT_URL}/reset-password',
        json={
            'token': token_reset,
            'new_password': '@novaSenhaDiferente123',
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Senha redefinida com sucesso.'}


def test_reset_password_invalid_token(client):
    response = client.post(
        f'{ENDPOINT_URL}/reset-password',
        json={
            'token': 'token totalmente inválido',
            'new_password': '@SenhaValida123',
        },
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Token inválido.'}


@pytest.mark.parametrize(
    'weak_password',
    [
        'Ab1!xyz',
        'Abcdefg!',
        'ABCDEFG1!',
        'abcdefg1!',
        'Abcdefg1',
        'Aa1!' + 'a' * 61,
    ],
)
def test_reset_password_senha_fraca(client, weak_password):
    response = client.post(
        f'{ENDPOINT_URL}/reset-password',
        json={'token': 'token-invalido', 'new_password': weak_password},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_reset_password_wrong_purpose(
    client, session, user, token_factory
):
    token = token_factory(user.id, purpose='login')

    db_reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        used=False,
    )

    session.add(db_reset_token)
    await session.commit()

    response = client.post(
        f'{ENDPOINT_URL}/reset-password',
        json={'token': token, 'new_password': 'NovaSenha123!'},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Token inválido ou expirado.'}


@pytest.mark.asyncio
async def test_reset_password_expired_token(
    client, session, user, token_factory
):
    with freeze_time('2025-01-01 10:00:00'):
        token = token_factory(
            user.id, purpose='password_reset', expire_minutes=5
        )

        db_reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
            used=False,
        )

        session.add(db_reset_token)
        await session.commit()

    with freeze_time('2025-01-01 10:06:00'):
        response = client.post(
            f'{ENDPOINT_URL}/reset-password',
            json={'token': token, 'new_password': '@SenhaValida123'},
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json() == {'detail': 'Token expirado.'}


@pytest.mark.asyncio
async def test_reset_password_same_as_old(
    client, session, user, token_factory
):
    token = token_factory(user.id, purpose='password_reset')

    db_reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        used=False,
    )

    session.add(db_reset_token)
    await session.commit()

    response = client.post(
        f'{ENDPOINT_URL}/reset-password',
        json={
            'token': token,
            'new_password': user.clean_password,
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        'detail': 'A nova senha não pode ser igual a anterior.'
    }


@pytest.mark.asyncio
async def test_reset_password_user_not_found(
    client, session, user, token_factory
):
    token = token_factory('9999', purpose='password_reset')

    db_reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        used=False,
    )
    session.add(db_reset_token)
    await session.commit()

    response = client.post(
        f'{ENDPOINT_URL}/reset-password',
        json={'token': token, 'new_password': '@SenhaValida123'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {'detail': 'Usuário não encontrado.'}


@pytest.mark.asyncio
async def test_login_persiste_refresh_token(client, session, user):
    response = client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': user.clean_password},
    )

    assert response.status_code == HTTPStatus.OK

    db_token = await session.scalar(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )

    assert db_token is not None
    assert db_token.rotated_at is None
    assert db_token.session_started_at is not None


def test_refresh_rotaciona_token(client, user):
    client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    old_token = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    response = client.post(f'{ENDPOINT_URL}/refresh_token')

    assert response.status_code == HTTPStatus.OK
    assert client.cookies.get(settings.REFRESH_COOKIE_NAME) != old_token


def test_rotacao_nao_estende_limite_absoluto(client, user):
    with freeze_time('2025-09-17 12:00:00') as frozen:
        client.post(
            f'{ENDPOINT_URL}/token',
            data={
                'username': user.username,
                'password': user.clean_password,
            },
        )

        frozen.tick(timedelta(days=6))
        rotated = client.post(f'{ENDPOINT_URL}/refresh_token')
        assert rotated.status_code == HTTPStatus.OK

        rotated_refresh = client.cookies.get(settings.REFRESH_COOKIE_NAME)

        frozen.tick(timedelta(days=2))
        response = _refresh_with(client, rotated_refresh)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_reuso_de_refresh_token_encerra_sessoes(client, user):
    client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    old_token = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    client.post(f'{ENDPOINT_URL}/refresh_token')
    new_token = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    replay = _refresh_with(client, old_token)
    assert replay.status_code == HTTPStatus.UNAUTHORIZED

    response = _refresh_with(client, new_token)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_logout_invalida_refresh_token_no_servidor(client, user):
    client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    refresh_token = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    response = client.post(f'{ENDPOINT_URL}/logout')
    assert response.status_code == HTTPStatus.NO_CONTENT

    assert (
        _refresh_with(client, refresh_token).status_code
        == HTTPStatus.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_reset_password_revoga_refresh_tokens(
    client, session, user, token_factory
):
    client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    refresh_token = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    token_reset = token_factory(user.id, purpose='password_reset')
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token=token_reset,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
            used=False,
        )
    )
    await session.commit()

    response = client.post(
        f'{ENDPOINT_URL}/reset-password',
        json={
            'token': token_reset,
            'new_password': '@novaSenhaDiferente123',
        },
    )
    assert response.status_code == HTTPStatus.OK

    assert (
        _refresh_with(client, refresh_token).status_code
        == HTTPStatus.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_reset_password_invalida_access_token_anterior(
    client, session, user, token_factory
):
    with freeze_time('2025-09-17 12:00:00') as frozen:
        login = client.post(
            f'{ENDPOINT_URL}/token',
            data={
                'username': user.username,
                'password': user.clean_password,
            },
        )
        old_access = login.json()['access_token']

        frozen.move_to('2025-09-17 12:00:05.500000')

        token_reset = token_factory(user.id, purpose='password_reset')
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token=token_reset,
                expires_at=datetime.now(UTC)
                + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
                used=False,
            )
        )
        await session.commit()

        response = client.post(
            f'{ENDPOINT_URL}/reset-password',
            json={
                'token': token_reset,
                'new_password': '@novaSenhaDiferente123',
            },
        )
        assert response.status_code == HTTPStatus.OK

        protected = client.get('/api/v1/users/me', headers=_auth(old_access))

    assert protected.status_code == HTTPStatus.UNAUTHORIZED


def test_refresh_token_expirado(client, user):
    with freeze_time('2025-09-18 12:00:00'):
        client.post(
            f'{ENDPOINT_URL}/token',
            data={
                'username': user.username,
                'password': user.clean_password,
            },
        )
        refresh_token = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    with freeze_time('2025-09-26 12:00:00'):
        response = _refresh_with(client, refresh_token)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
