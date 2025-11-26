from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from freezegun import freeze_time

from internum.core.settings import Settings
from internum.modules.auth.models import PasswordResetToken

settings = Settings()

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
    assert response.json() == {'detail': 'Email ou senha incorretos'}


def test_token_wrong_password(client, user):
    response = client.post(
        f'{ENDPOINT_URL}/token',
        data={'username': user.username, 'password': 'wrong_password'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Email ou senha incorretos'}


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
            'new_password': 'aaaaaa',
        },
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Token inválido.'}


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
            json={'token': token, 'new_password': 'aaaaaa'},
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
        json={'token': token, 'new_password': 'aaaaaa'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {'detail': 'Usuário não encontrado.'}
