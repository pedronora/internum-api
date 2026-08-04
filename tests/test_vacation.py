from datetime import date
from http import HTTPStatus

import pytest_asyncio
from freezegun import freeze_time

from internum.core.security import get_password_hash
from internum.modules.users.enums import Role
from internum.modules.users.models import User
from internum.modules.vacation.services import CLTVacationService
from tests.conftest import UserFactory

ENDPOINT_URL = '/api/v1/vacation'
AUTH_URL = '/api/v1/auth/token'

HIRING_DATE = date(2024, 1, 10)
FROZEN_NOW = '2025-05-21 10:00:00'

MAIN_PERIOD = {'start_date': '2025-06-12', 'end_date': '2025-06-25'}
MAIN_WORK_DAYS = 10
MAIN_CAL_DAYS = 14
PROP_PERIOD = {'start_date': '2025-08-04', 'end_date': '2025-08-08'}
PROP_WORK_DAYS = 5
PROP_CAL_DAYS = 5

WEEKEND_START_PERIOD = {'start_date': '2025-06-07', 'end_date': '2025-06-13'}
WEEKEND_START_CAL_DAYS = 7
WEEKEND_START_WORK_DAYS = 5

VACATION_YEAR_DAYS = 30
SELL_DAYS = 10
ADJUST_DAYS = 10
ADJUST_REASON = 'Migração de saldo histórico'


def build_user(**overrides) -> User:
    user = UserFactory(hiring_date=HIRING_DATE, **overrides)
    plain_password = user.password
    user.password = get_password_hash(plain_password)
    user.clean_password = plain_password
    return user


@pytest_asyncio.fixture
async def vacation_user(session) -> User:
    user = build_user(role=Role.USER)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def vacation_other(session) -> User:
    user = build_user(role=Role.USER)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def vacation_coord(session) -> User:
    user = build_user(role=Role.COORD)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def vacation_admin(session) -> User:
    user = build_user(role=Role.ADMIN)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def auth_headers(client, user: User) -> dict:
    response = client.post(
        AUTH_URL,
        data={'username': user.username, 'password': user.clean_password},
    )
    assert response.status_code == HTTPStatus.OK
    return {'Authorization': f'Bearer {response.json()["access_token"]}'}


def create_request(client, headers, periods) -> int:
    response = client.post(
        ENDPOINT_URL + '/requests',
        headers=headers,
        json={'periods': periods},
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()['id']


# --- Service unit tests ---------------------------------------------------


def test_service_is_weekend():
    service = CLTVacationService(None)
    assert service.is_weekend(date(2025, 6, 7))
    assert not service.is_weekend(date(2025, 6, 9))


def test_service_is_holiday():
    service = CLTVacationService(None)
    assert service.is_holiday(date(2025, 5, 1))
    assert not service.is_holiday(date(2025, 6, 12))


def test_service_count_working_days():
    service = CLTVacationService(None)
    result = service.count_working_days(date(2025, 6, 12), date(2025, 6, 25))
    assert result == MAIN_WORK_DAYS


# --- Balance --------------------------------------------------------------


def test_balance_requires_auth(client):
    response = client.get(ENDPOINT_URL + '/balance')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@freeze_time(FROZEN_NOW)
def test_get_my_balance(client, vacation_user):
    response = client.get(
        ENDPOINT_URL + '/balance', headers=auth_headers(client, vacation_user)
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['user_id'] == vacation_user.id
    assert data['accrued_days'] == VACATION_YEAR_DAYS
    assert data['proportional_days'] == 0
    assert data['available_days'] == VACATION_YEAR_DAYS
    assert data['manual_adjustment_days'] == 0


@freeze_time(FROZEN_NOW)
def test_get_user_balance_as_admin(client, vacation_user, vacation_admin):
    response = client.get(
        f'{ENDPOINT_URL}/balance/{vacation_user.id}',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['user_id'] == vacation_user.id


@freeze_time(FROZEN_NOW)
def test_get_user_balance_forbidden_for_user(
    client, vacation_user, vacation_other
):
    response = client.get(
        f'{ENDPOINT_URL}/balance/{vacation_user.id}',
        headers=auth_headers(client, vacation_other),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_get_user_balance_not_found(client, vacation_admin):
    response = client.get(
        f'{ENDPOINT_URL}/balance/999999',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


# --- Preview --------------------------------------------------------------


@freeze_time(FROZEN_NOW)
def test_preview_valid(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=auth_headers(client, vacation_user),
        json={'periods': [MAIN_PERIOD, PROP_PERIOD]},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is True
    assert data['errors'] == []
    assert data['total_days'] == MAIN_CAL_DAYS + PROP_CAL_DAYS
    assert data['total_working_days'] == MAIN_WORK_DAYS + PROP_WORK_DAYS
    assert len(data['periods_detail']) == len([MAIN_PERIOD, PROP_PERIOD])
    assert data['periods_detail'][0]['period_type'] == 'full'
    assert data['periods_detail'][1]['period_type'] == 'proportional'


@freeze_time(FROZEN_NOW)
def test_preview_start_on_weekend(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=auth_headers(client, vacation_user),
        json={'periods': [WEEKEND_START_PERIOD]},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('fim de semana' in error for error in data['errors'])
    assert data['total_days'] == WEEKEND_START_CAL_DAYS
    assert data['total_working_days'] == WEEKEND_START_WORK_DAYS
    assert len(data['periods_detail']) == 1


@freeze_time(FROZEN_NOW)
def test_preview_start_on_holiday(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=auth_headers(client, vacation_user),
        json={
            'periods': [{'start_date': '2025-05-01', 'end_date': '2025-05-09'}]
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('não pode ser em feriado' in error for error in data['errors'])


@freeze_time(FROZEN_NOW)
def test_preview_period_too_short(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=auth_headers(client, vacation_user),
        json={
            'periods': [{'start_date': '2025-06-09', 'end_date': '2025-06-12'}]
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any(
        'no mínimo 5 dias corridos' in error for error in data['errors']
    )


@freeze_time(FROZEN_NOW)
def test_preview_no_main_period(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=auth_headers(client, vacation_user),
        json={
            'periods': [
                {'start_date': '2025-07-07', 'end_date': '2025-07-11'},
                {'start_date': '2025-07-14', 'end_date': '2025-07-18'},
            ]
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('14 dias ou mais' in error for error in data['errors'])


@freeze_time(FROZEN_NOW)
def test_preview_over_30_working_days(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=auth_headers(client, vacation_user),
        json={
            'periods': [{'start_date': '2025-06-02', 'end_date': '2025-07-14'}]
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any(
        'excede o máximo de 30 dias' in error for error in data['errors']
    )


@freeze_time(FROZEN_NOW)
def test_preview_more_than_three_periods(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=auth_headers(client, vacation_user),
        json={'periods': [MAIN_PERIOD, PROP_PERIOD, PROP_PERIOD, PROP_PERIOD]},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@freeze_time(FROZEN_NOW)
def test_preview_end_before_start(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=auth_headers(client, vacation_user),
        json={
            'periods': [{'start_date': '2025-06-12', 'end_date': '2025-06-11'}]
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- Requests workflow ----------------------------------------------------


@freeze_time(FROZEN_NOW)
def test_create_vacation_request(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/requests',
        headers=auth_headers(client, vacation_user),
        json={'periods': [MAIN_PERIOD]},
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['user_id'] == vacation_user.id
    assert data['status'] == 'submitted'
    assert len(data['periods']) == 1
    period = data['periods'][0]
    assert period['start_date'] == MAIN_PERIOD['start_date']
    assert period['end_date'] == MAIN_PERIOD['end_date']
    assert period['days_count'] == MAIN_CAL_DAYS
    assert period['working_days_count'] == MAIN_WORK_DAYS
    assert period['period_type'] == 'full'
    assert period['status'] == 'pending'


@freeze_time(FROZEN_NOW)
def test_get_request_details(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    response = client.get(
        f'{ENDPOINT_URL}/requests/{request_id}', headers=headers
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['id'] == request_id
    assert data['user_id'] == vacation_user.id
    assert data['status'] == 'submitted'
    assert data['periods'][0]['working_days_count'] == MAIN_WORK_DAYS


@freeze_time(FROZEN_NOW)
def test_get_other_user_request_forbidden(
    client, vacation_user, vacation_other
):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    response = client.get(
        f'{ENDPOINT_URL}/requests/{request_id}',
        headers=auth_headers(client, vacation_other),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_list_requests(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    admin_headers = auth_headers(client, vacation_admin)
    response = client.get(ENDPOINT_URL + '/requests', headers=admin_headers)
    assert response.status_code == HTTPStatus.OK
    items = response.json()
    assert len(items) == 1
    assert items[0]['id'] == request_id
    assert items[0]['user_id'] == vacation_user.id
    assert items[0]['total_days'] == MAIN_CAL_DAYS
    assert items[0]['periods_count'] == 1


@freeze_time(FROZEN_NOW)
def test_list_requests_filtered_by_status(
    client, vacation_user, vacation_admin
):
    headers = auth_headers(client, vacation_user)
    create_request(client, headers, [MAIN_PERIOD])

    response = client.get(
        ENDPOINT_URL + '/requests?status=submitted',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 1

    response = client.get(
        ENDPOINT_URL + '/requests?status=approved',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


@freeze_time(FROZEN_NOW)
def test_submit_already_submitted(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/submit', headers=headers
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@freeze_time(FROZEN_NOW)
def test_update_request_not_draft(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    response = client.put(
        f'{ENDPOINT_URL}/requests/{request_id}',
        headers=headers,
        json={'reviewer_notes': 'novo'},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@freeze_time(FROZEN_NOW)
def test_approve_request_updates_balance(
    client, vacation_user, vacation_coord
):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD, PROP_PERIOD])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=auth_headers(client, vacation_coord),
        json={'action': 'approve', 'reviewer_notes': 'Aprovado'},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['status'] == 'approved'
    assert data['reviewer_id'] == vacation_coord.id
    assert all(period['status'] == 'approved' for period in data['periods'])

    balance = client.get(ENDPOINT_URL + '/balance', headers=headers).json()
    assert balance['enjoyed_days'] == MAIN_WORK_DAYS + PROP_WORK_DAYS
    assert balance['available_days'] == 30 - (MAIN_WORK_DAYS + PROP_WORK_DAYS)


@freeze_time(FROZEN_NOW)
def test_approve_requires_admin_or_coord(
    client, vacation_user, vacation_other
):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=auth_headers(client, vacation_other),
        json={'action': 'approve'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_reject_request(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/reject',
        headers=auth_headers(client, vacation_admin),
        json={'action': 'reject', 'reviewer_notes': 'Sem saldo'},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['status'] == 'rejected'
    assert data['reviewer_id'] == vacation_admin.id
    assert all(period['status'] == 'rejected' for period in data['periods'])


@freeze_time(FROZEN_NOW)
def test_cancel_own_request(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/cancel', headers=headers
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'cancelled'


@freeze_time(FROZEN_NOW)
def test_cancel_other_user_request(client, vacation_user, vacation_other):
    headers = auth_headers(client, vacation_user)
    request_id = create_request(client, headers, [MAIN_PERIOD])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/cancel',
        headers=auth_headers(client, vacation_other),
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == (
        'Não pode cancelar solicitação de outro usuário'
    )


# --- Sell days ------------------------------------------------------------


@freeze_time(FROZEN_NOW)
def test_sell_days(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/sell-days',
        headers=auth_headers(client, vacation_user),
        json={'days': 10},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['sold_days'] == SELL_DAYS
    assert data['accrued_days'] == VACATION_YEAR_DAYS - SELL_DAYS


@freeze_time(FROZEN_NOW)
def test_sell_days_above_limit(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/sell-days',
        headers=auth_headers(client, vacation_user),
        json={'days': 11},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@freeze_time(FROZEN_NOW)
def test_sell_days_zero(client, vacation_user):
    response = client.post(
        ENDPOINT_URL + '/sell-days',
        headers=auth_headers(client, vacation_user),
        json={'days': 0},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- Manual adjustment (admin) --------------------------------------------


@freeze_time(FROZEN_NOW)
def test_adjust_balance(client, vacation_user, vacation_admin):
    response = client.put(
        f'{ENDPOINT_URL}/balance/{vacation_user.id}/adjust',
        headers=auth_headers(client, vacation_admin),
        json={
            'manual_adjustment_days': ADJUST_DAYS,
            'adjustment_reason': ADJUST_REASON,
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['manual_adjustment_days'] == ADJUST_DAYS
    assert data['adjustment_reason'] == ADJUST_REASON
    assert data['available_days'] == VACATION_YEAR_DAYS + ADJUST_DAYS
    assert data['adjusted_by_id'] == vacation_admin.id


@freeze_time(FROZEN_NOW)
def test_adjust_balance_requires_admin(client, vacation_user, vacation_coord):
    response = client.put(
        f'{ENDPOINT_URL}/balance/{vacation_user.id}/adjust',
        headers=auth_headers(client, vacation_coord),
        json={
            'manual_adjustment_days': ADJUST_DAYS,
            'adjustment_reason': ADJUST_REASON,
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_adjust_balance_user_not_found(client, vacation_admin):
    response = client.put(
        f'{ENDPOINT_URL}/balance/999999/adjust',
        headers=auth_headers(client, vacation_admin),
        json={
            'manual_adjustment_days': ADJUST_DAYS,
            'adjustment_reason': ADJUST_REASON,
        },
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@freeze_time(FROZEN_NOW)
def test_adjust_balance_above_cap(client, vacation_user, vacation_admin):
    response = client.put(
        f'{ENDPOINT_URL}/balance/{vacation_user.id}/adjust',
        headers=auth_headers(client, vacation_admin),
        json={
            'manual_adjustment_days': 200,
            'adjustment_reason': ADJUST_REASON,
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'Teto máximo' in response.json()['detail']


@freeze_time(FROZEN_NOW)
def test_adjust_balance_below_minimum(client, vacation_user, vacation_admin):
    response = client.put(
        f'{ENDPOINT_URL}/balance/{vacation_user.id}/adjust',
        headers=auth_headers(client, vacation_admin),
        json={
            'manual_adjustment_days': -100,
            'adjustment_reason': 'Correção de saldo devedor',
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'negativos' in response.json()['detail']


@freeze_time(FROZEN_NOW)
def test_adjust_balance_reason_too_short(
    client, vacation_user, vacation_admin
):
    response = client.put(
        f'{ENDPOINT_URL}/balance/{vacation_user.id}/adjust',
        headers=auth_headers(client, vacation_admin),
        json={'manual_adjustment_days': 5, 'adjustment_reason': 'ab'},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
