from datetime import date
from http import HTTPStatus

import pytest
import pytest_asyncio
from fastapi._compat import get_cached_model_fields  # noqa: PLC2701
from freezegun import freeze_time

from internum.core.security import get_password_hash
from internum.modules.users.enums import Role, Setor
from internum.modules.users.models import User
from internum.modules.vacation import schemas as vacation_schemas
from internum.modules.vacation.services import CLTVacationService
from tests.conftest import UserFactory

ENDPOINT_URL = '/api/v1/vacation'
AUTH_URL = '/api/v1/auth/token'

HIRING_DATE = date(2024, 1, 10)
OLD_HIRING_DATE = date(2021, 1, 10)
FROZEN_NOW = '2025-05-21 10:00:00'

MAIN_PERIOD = {'start_date': '2025-06-12', 'end_date': '2025-06-25'}
MAIN_CAL_DAYS = 14
PROP_PERIOD = {'start_date': '2025-08-04', 'end_date': '2025-08-08'}
PROP_CAL_DAYS = 5

WEEKEND_START_PERIOD = {'start_date': '2025-06-07', 'end_date': '2025-06-13'}

VACATION_YEAR_DAYS = 30
SELL_DAYS = 10
EXPECTED_PROPORTIONAL_DAYS = 10
TOTAL_ACCRUAL_PERIODS = 2
RETROACTIVE_DAYS = 5
DOUBLE_PAYMENT_DAYS = 10
EXPIRED_PERIODS_COUNT = 3


@pytest.fixture(scope='session', autouse=True)
def warm_fastapi_schemas():
    """Pré-compila schemas fora de freeze_time (freezegun quebra pydantic)."""
    for name in (
        'VacationReviewRequest',
        'VacationAccrualPeriodAlert',
        'VacationAccrualPeriodRead',
        'VacationConfirmFruitionRequest',
        'VacationGrantAdminCreate',
        'VacationGrantCreate',
        'VacationGrantRead',
        'VacationPeriodCreate',
        'VacationPreviewRequest',
        'VacationPreviewResponse',
        'VacationRequestCreate',
        'VacationRequestListItem',
        'VacationRequestRead',
        'VacationSellDaysRequest',
    ):
        get_cached_model_fields(getattr(vacation_schemas, name))


def build_user(**overrides) -> User:
    defaults = {'hiring_date': HIRING_DATE}
    defaults.update(overrides)
    user = UserFactory(**defaults)
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
async def vacation_old_user(session) -> User:
    user = build_user(role=Role.USER, hiring_date=OLD_HIRING_DATE)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def about_to_expire_user(session) -> User:
    user = build_user(role=Role.USER, hiring_date=date(2023, 6, 16))
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


def get_accrual_periods(client, headers) -> list[dict]:
    response = client.get(ENDPOINT_URL + '/accrual-periods', headers=headers)
    assert response.status_code == HTTPStatus.OK
    return response.json()


def get_period_by_status(client, headers, status: str) -> dict:
    periods = get_accrual_periods(client, headers)
    for period in periods:
        if period['status'] == status:
            return period
    raise AssertionError(f'Período com status {status} não encontrado')


def create_request(client, headers, periods, target_id: int) -> int:
    response = client.post(
        ENDPOINT_URL + '/requests',
        headers=headers,
        json={'target_accrual_period_id': target_id, 'periods': periods},
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


def test_service_count_calendar_days():
    service = CLTVacationService(None)
    result = service.count_calendar_days(date(2025, 6, 12), date(2025, 6, 25))
    assert result == MAIN_CAL_DAYS


def test_service_anniversary_leap_year():
    service = CLTVacationService(None)
    assert service._anniversary(date(2020, 2, 29), 1) == date(2021, 2, 28)
    assert service._anniversary(date(2020, 2, 29), 4) == date(2024, 2, 29)


def test_service_period_dates():
    service = CLTVacationService(None)
    as_start, as_end, cs_start, cs_end = service._period_dates(HIRING_DATE, 1)
    assert as_start == date(2024, 1, 10)
    assert as_end == date(2025, 1, 9)
    assert cs_start == date(2025, 1, 10)
    assert cs_end == date(2026, 1, 9)


# --- Accrual periods ------------------------------------------------------


def test_accrual_periods_requires_auth(client):
    response = client.get(ENDPOINT_URL + '/accrual-periods')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@freeze_time(FROZEN_NOW)
def test_my_accrual_periods(client, vacation_user):
    periods = get_accrual_periods(client, auth_headers(client, vacation_user))
    assert len(periods) == TOTAL_ACCRUAL_PERIODS

    first, second = periods
    assert first['period_number'] == 1
    assert first['status'] == 'concessive'
    assert first['days_earned'] == VACATION_YEAR_DAYS
    assert first['available_days'] == VACATION_YEAR_DAYS

    assert second['period_number'] == 2  # noqa: PLR2004
    assert second['status'] == 'acquisitive'
    assert second['days_earned'] == EXPECTED_PROPORTIONAL_DAYS
    assert second['available_days'] == EXPECTED_PROPORTIONAL_DAYS


@freeze_time(FROZEN_NOW)
def test_admin_view_user_accrual_periods(
    client, vacation_user, vacation_admin
):
    response = client.get(
        f'{ENDPOINT_URL}/accrual-periods/{vacation_user.id}',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == TOTAL_ACCRUAL_PERIODS


@freeze_time(FROZEN_NOW)
def test_view_other_user_periods_forbidden(
    client, vacation_user, vacation_other
):
    response = client.get(
        f'{ENDPOINT_URL}/accrual-periods/{vacation_user.id}',
        headers=auth_headers(client, vacation_other),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_user_accrual_periods_not_found(client, vacation_admin):
    response = client.get(
        f'{ENDPOINT_URL}/accrual-periods/999999',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


# --- Preview --------------------------------------------------------------


@freeze_time(FROZEN_NOW)
def test_preview_valid(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [MAIN_PERIOD, PROP_PERIOD],
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is True
    assert data['errors'] == []
    assert data['total_days'] == MAIN_CAL_DAYS + PROP_CAL_DAYS
    assert len(data['periods_detail']) == TOTAL_ACCRUAL_PERIODS
    assert data['periods_detail'][0]['period_type'] == 'main'
    assert data['periods_detail'][1]['period_type'] == 'complementary'


@freeze_time(FROZEN_NOW)
def test_preview_start_on_weekend(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [WEEKEND_START_PERIOD],
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('sexta, sábado ou domingo' in e for e in data['errors'])


@freeze_time(FROZEN_NOW)
def test_preview_start_on_holiday(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [
                {'start_date': '2025-05-01', 'end_date': '2025-05-09'}
            ],
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('não pode ser em feriado' in e for e in data['errors'])


@freeze_time(FROZEN_NOW)
def test_preview_period_too_short(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [
                {'start_date': '2025-06-09', 'end_date': '2025-06-12'}
            ],
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('no mínimo 5 dias corridos' in e for e in data['errors'])


@freeze_time(FROZEN_NOW)
def test_preview_exceeds_balance(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [
                {'start_date': '2025-06-02', 'end_date': '2025-07-02'}
            ],
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('excedem saldo disponível' in e for e in data['errors'])


@freeze_time(FROZEN_NOW)
def test_preview_remaining_below_minimum(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [
                {'start_date': '2025-06-02', 'end_date': '2025-06-29'}
            ],
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('Restariam 2 dias' in e for e in data['errors'])


@freeze_time(FROZEN_NOW)
def test_preview_remaining_needs_full_period(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [
                {'start_date': '2025-06-12', 'end_date': '2025-06-21'},
                {'start_date': '2025-06-23', 'end_date': '2025-07-02'},
            ],
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('Sem período de 14 dias ainda' in e for e in data['errors'])


@freeze_time(FROZEN_NOW)
def test_preview_more_than_three_periods(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [MAIN_PERIOD, PROP_PERIOD, PROP_PERIOD, PROP_PERIOD],
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@freeze_time(FROZEN_NOW)
def test_preview_end_before_start(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [
                {'start_date': '2025-06-12', 'end_date': '2025-06-11'}
            ],
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@freeze_time(FROZEN_NOW)
def test_preview_expired_period(client, vacation_old_user):
    headers = auth_headers(client, vacation_old_user)
    period = get_period_by_status(client, headers, 'expired')
    response = client.post(
        ENDPOINT_URL + '/preview',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [MAIN_PERIOD],
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['valid'] is False
    assert any('concessivo expirado' in e for e in data['errors'])


# --- Requests workflow ----------------------------------------------------


@freeze_time(FROZEN_NOW)
def test_create_vacation_request(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(
        client, headers, [MAIN_PERIOD, PROP_PERIOD], period['id']
    )

    response = client.get(
        f'{ENDPOINT_URL}/requests/{request_id}', headers=headers
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['user_id'] == vacation_user.id
    assert data['target_accrual_period_id'] == period['id']
    assert data['status'] == 'submitted'
    assert len(data['periods']) == TOTAL_ACCRUAL_PERIODS
    first = data['periods'][0]
    assert first['start_date'] == MAIN_PERIOD['start_date']
    assert first['end_date'] == MAIN_PERIOD['end_date']
    assert first['days_count'] == MAIN_CAL_DAYS
    assert first['period_type'] == 'main'


@freeze_time(FROZEN_NOW)
def test_create_request_requires_auth(client):
    response = client.post(
        ENDPOINT_URL + '/requests',
        json={'target_accrual_period_id': 1, 'periods': [MAIN_PERIOD]},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@freeze_time(FROZEN_NOW)
def test_create_request_exceeds_balance(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'acquisitive')
    response = client.post(
        ENDPOINT_URL + '/requests',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [MAIN_PERIOD],
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'excedem saldo disponível' in response.json()['detail']


@freeze_time(FROZEN_NOW)
def test_create_request_weekend_start(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        ENDPOINT_URL + '/requests',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [WEEKEND_START_PERIOD],
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'sexta, sábado ou domingo' in response.json()['detail']


@freeze_time(FROZEN_NOW)
def test_create_request_expired_period(client, vacation_old_user):
    headers = auth_headers(client, vacation_old_user)
    period = get_period_by_status(client, headers, 'expired')
    response = client.post(
        ENDPOINT_URL + '/requests',
        headers=headers,
        json={
            'target_accrual_period_id': period['id'],
            'periods': [MAIN_PERIOD],
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'concessivo expirado' in response.json()['detail']


@freeze_time(FROZEN_NOW)
def test_get_other_user_request_forbidden(
    client, vacation_user, vacation_other
):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])

    response = client.get(
        f'{ENDPOINT_URL}/requests/{request_id}',
        headers=auth_headers(client, vacation_other),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_list_requests(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])

    response = client.get(
        ENDPOINT_URL + '/requests',
        headers=auth_headers(client, vacation_admin),
    )
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
    period = get_period_by_status(client, headers, 'concessive')
    create_request(client, headers, [MAIN_PERIOD], period['id'])

    admin_headers = auth_headers(client, vacation_admin)
    response = client.get(
        ENDPOINT_URL + '/requests?status=submitted',
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 1

    response = client.get(
        ENDPOINT_URL + '/requests?status=approved',
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


@freeze_time(FROZEN_NOW)
def test_approve_requires_admin_or_coord(
    client, vacation_user, vacation_other
):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=auth_headers(client, vacation_other),
        json={},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_reject_request(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/reject',
        headers=auth_headers(client, vacation_admin),
        json={'reviewer_notes': 'Sem saldo'},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['status'] == 'rejected'
    assert data['reviewer_id'] == vacation_admin.id


@freeze_time(FROZEN_NOW)
def test_reject_after_approve(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])

    client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=auth_headers(client, vacation_admin),
        json={},
    )
    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/reject',
        headers=auth_headers(client, vacation_admin),
        json={},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@freeze_time(FROZEN_NOW)
def test_cancel_own_request(client, vacation_user):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/cancel', headers=headers
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'cancelled'


@freeze_time(FROZEN_NOW)
def test_cancel_other_user_request(client, vacation_user, vacation_other):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/cancel',
        headers=auth_headers(client, vacation_other),
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail'] == (
        'Não pode cancelar solicitação de outro usuário'
    )


# --- Grants ---------------------------------------------------------------


@freeze_time(FROZEN_NOW)
def test_approve_creates_grant_and_reserves(
    client, vacation_user, vacation_coord
):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(
        client, headers, [MAIN_PERIOD, PROP_PERIOD], period['id']
    )

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=auth_headers(client, vacation_coord),
        json={'reviewer_notes': 'Aprovado'},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['status'] == 'approved'
    assert data['reviewer_id'] == vacation_coord.id

    updated = get_accrual_periods(client, headers)
    period = next(p for p in updated if p['id'] == period['id'])
    assert period['days_reserved'] == MAIN_CAL_DAYS + PROP_CAL_DAYS
    assert period['available_days'] == VACATION_YEAR_DAYS - (
        MAIN_CAL_DAYS + PROP_CAL_DAYS
    )

    grants = client.get(
        ENDPOINT_URL + '/grants', headers=auth_headers(client, vacation_user)
    ).json()
    assert len(grants) == TOTAL_ACCRUAL_PERIODS
    assert all(g['status'] == 'granted' for g in grants)
    assert all(g['grant_type'] == 'normal' for g in grants)
    assert sum(g['days_count'] for g in grants) == (
        MAIN_CAL_DAYS + PROP_CAL_DAYS
    )


@freeze_time(FROZEN_NOW)
def test_approve_insufficient_balance(client, vacation_user, vacation_coord):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    first_id = create_request(
        client,
        headers,
        [{'start_date': '2025-06-12', 'end_date': '2025-07-01'}],
        period['id'],
    )
    second_id = create_request(
        client,
        headers,
        [{'start_date': '2025-07-03', 'end_date': '2025-07-22'}],
        period['id'],
    )

    approve_url = f'{ENDPOINT_URL}/requests/{{id}}/approve'
    coord_headers = auth_headers(client, vacation_coord)
    response = client.post(
        approve_url.format(id=first_id),
        headers=coord_headers,
        json={},
    )
    assert response.status_code == HTTPStatus.OK

    response = client.post(
        approve_url.format(id=second_id),
        headers=coord_headers,
        json={},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'Saldo insuficiente' in response.json()['detail']


@freeze_time(FROZEN_NOW)
def test_confirm_fruition(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])
    coord_headers = auth_headers(client, vacation_admin)
    client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=coord_headers,
        json={},
    )

    grant = client.get(
        ENDPOINT_URL + '/grants', headers=auth_headers(client, vacation_user)
    ).json()[0]
    response = client.post(
        f'{ENDPOINT_URL}/grants/{grant["id"]}/confirm-fruition',
        headers=coord_headers,
        json={'confirm': True},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'fruited'

    updated = get_accrual_periods(client, headers)
    period = next(p for p in updated if p['id'] == period['id'])
    assert period['days_enjoyed'] == MAIN_CAL_DAYS
    assert period['days_reserved'] == 0
    assert period['available_days'] == VACATION_YEAR_DAYS - MAIN_CAL_DAYS


@freeze_time(FROZEN_NOW)
def test_confirm_fruition_denied(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])
    admin_headers = auth_headers(client, vacation_admin)
    client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=admin_headers,
        json={},
    )

    grant = client.get(
        ENDPOINT_URL + '/grants', headers=auth_headers(client, vacation_user)
    ).json()[0]
    response = client.post(
        f'{ENDPOINT_URL}/grants/{grant["id"]}/confirm-fruition',
        headers=admin_headers,
        json={'confirm': False},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'cancelled'

    updated = get_accrual_periods(client, headers)
    period = next(p for p in updated if p['id'] == period['id'])
    assert period['days_reserved'] == 0
    assert period['available_days'] == VACATION_YEAR_DAYS


@freeze_time(FROZEN_NOW)
def test_confirm_fruition_requires_admin_or_coord(
    client, vacation_user, vacation_coord, vacation_other
):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])
    client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=auth_headers(client, vacation_coord),
        json={},
    )

    grant = client.get(
        ENDPOINT_URL + '/grants', headers=auth_headers(client, vacation_user)
    ).json()[0]

    response = client.post(
        f'{ENDPOINT_URL}/grants/{grant["id"]}/confirm-fruition',
        headers=auth_headers(client, vacation_other),
        json={'confirm': True},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN

    response = client.post(
        f'{ENDPOINT_URL}/grants/{grant["id"]}/confirm-fruition',
        headers=auth_headers(client, vacation_coord),
        json={'confirm': True},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'fruited'


@freeze_time(FROZEN_NOW)
def test_get_grant_forbidden_for_other_user(
    client, vacation_user, vacation_other, vacation_coord
):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])
    client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=auth_headers(client, vacation_coord),
        json={},
    )
    grant = client.get(ENDPOINT_URL + '/grants', headers=headers).json()[0]

    response = client.get(
        f'{ENDPOINT_URL}/grants/{grant["id"]}',
        headers=auth_headers(client, vacation_other),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


# --- Admin grants (retroactive / double payment) --------------------------


@freeze_time(FROZEN_NOW)
def test_create_retroactive_grant(client, vacation_old_user, vacation_admin):
    headers = auth_headers(client, vacation_old_user)
    period = get_period_by_status(client, headers, 'expired')
    admin_headers = auth_headers(client, vacation_admin)

    response = client.post(
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_old_user.id}/{period["id"]}/grants',
        headers=admin_headers,
        json={
            'start_date': '2023-05-01',
            'end_date': '2023-05-05',
            'grant_type': 'retroactive',
            'notes': 'Gozo atrasado',
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['grant_type'] == 'retroactive'
    assert data['status'] == 'fruited'
    assert data['days_count'] == RETROACTIVE_DAYS

    updated = get_accrual_periods(client, headers)
    period = next(p for p in updated if p['id'] == period['id'])
    assert period['days_enjoyed'] == RETROACTIVE_DAYS
    assert period['days_reserved'] == 0
    assert period['is_double_eligible'] is True


@freeze_time(FROZEN_NOW)
def test_create_grant_requires_admin_or_coord(
    client, vacation_old_user, vacation_coord, vacation_other
):
    period = get_period_by_status(
        client, auth_headers(client, vacation_old_user), 'expired'
    )
    url = (
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_old_user.id}/{period["id"]}/grants'
    )
    payload = {
        'start_date': '2023-05-01',
        'end_date': '2023-05-05',
        'grant_type': 'retroactive',
    }

    response = client.post(
        url, headers=auth_headers(client, vacation_other), json=payload
    )
    assert response.status_code == HTTPStatus.FORBIDDEN

    response = client.post(
        url, headers=auth_headers(client, vacation_coord), json=payload
    )
    assert response.status_code == HTTPStatus.CREATED


@freeze_time(FROZEN_NOW)
def test_create_grant_on_non_expired_period(
    client, vacation_user, vacation_admin
):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    response = client.post(
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_user.id}/{period["id"]}/grants',
        headers=auth_headers(client, vacation_admin),
        json={
            'start_date': '2025-06-12',
            'end_date': '2025-06-21',
            'grant_type': 'double_payment',
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'concessivo expirado' in response.json()['detail']


@freeze_time(FROZEN_NOW)
def test_double_payment_flow(client, vacation_old_user, vacation_admin):
    headers = auth_headers(client, vacation_old_user)
    period = get_period_by_status(client, headers, 'expired')
    admin_headers = auth_headers(client, vacation_admin)

    response = client.post(
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_old_user.id}/{period["id"]}/grants',
        headers=admin_headers,
        json={
            'start_date': '2023-01-10',
            'end_date': '2023-01-19',
            'grant_type': 'double_payment',
            'notes': 'Dobro Art. 137',
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    grant = response.json()
    assert grant['status'] == 'paid_double'
    assert grant['days_count'] == DOUBLE_PAYMENT_DAYS

    updated = get_accrual_periods(client, headers)
    period = next(p for p in updated if p['id'] == period['id'])
    assert period['days_double_paid'] == DOUBLE_PAYMENT_DAYS
    assert period['days_reserved'] == 0


@freeze_time(FROZEN_NOW)
def test_retroactive_full_balance_closes_period(
    client, vacation_old_user, vacation_admin
):
    headers = auth_headers(client, vacation_old_user)
    period = get_period_by_status(client, headers, 'expired')
    admin_headers = auth_headers(client, vacation_admin)

    response = client.post(
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_old_user.id}/{period["id"]}/grants',
        headers=admin_headers,
        json={
            'start_date': '2022-01-10',
            'end_date': '2022-02-08',
            'grant_type': 'retroactive',
            'notes': 'Gozo integral atrasado',
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['status'] == 'fruited'

    updated = get_accrual_periods(client, headers)
    period = next(p for p in updated if p['id'] == period['id'])
    assert period['days_enjoyed'] == VACATION_YEAR_DAYS
    assert period['days_reserved'] == 0
    assert period['status'] == 'closed'
    assert period['is_double_eligible'] is False


@freeze_time(FROZEN_NOW)
def test_confirm_fruition_rejected_for_terminal_grant(
    client, vacation_old_user, vacation_admin
):
    headers = auth_headers(client, vacation_old_user)
    period = get_period_by_status(client, headers, 'expired')
    admin_headers = auth_headers(client, vacation_admin)

    response = client.post(
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_old_user.id}/{period["id"]}/grants',
        headers=admin_headers,
        json={
            'start_date': '2023-05-01',
            'end_date': '2023-05-05',
            'grant_type': 'retroactive',
        },
    )
    grant = response.json()
    response = client.post(
        f'{ENDPOINT_URL}/grants/{grant["id"]}/confirm-fruition',
        headers=admin_headers,
        json={'confirm': True},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


# --- Sell days ------------------------------------------------------------


@freeze_time(FROZEN_NOW)
def test_sell_days_by_admin(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')

    response = client.post(
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_user.id}/{period["id"]}/sell',
        headers=auth_headers(client, vacation_admin),
        json={'days': SELL_DAYS},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['days_sold'] == SELL_DAYS
    assert data['available_days'] == VACATION_YEAR_DAYS - SELL_DAYS


@freeze_time(FROZEN_NOW)
def test_sell_days_forbidden_for_user(client, vacation_user, vacation_other):
    period = get_period_by_status(
        client, auth_headers(client, vacation_user), 'concessive'
    )
    response = client.post(
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_user.id}/{period["id"]}/sell',
        headers=auth_headers(client, vacation_other),
        json={'days': SELL_DAYS},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_sell_days_above_limit(client, vacation_user, vacation_admin):
    period = get_period_by_status(
        client, auth_headers(client, vacation_user), 'concessive'
    )
    response = client.post(
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_user.id}/{period["id"]}/sell',
        headers=auth_headers(client, vacation_admin),
        json={'days': 11},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@freeze_time(FROZEN_NOW)
def test_sell_days_insufficient_balance(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'acquisitive')
    admin_headers = auth_headers(client, vacation_admin)
    sell_url = (
        f'{ENDPOINT_URL}/accrual-periods/'
        f'{vacation_user.id}/{period["id"]}/sell'
    )

    response = client.post(sell_url, headers=admin_headers, json={'days': 10})
    assert response.status_code == HTTPStatus.OK

    response = client.post(sell_url, headers=admin_headers, json={'days': 5})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'disponíveis' in response.json()['detail']


# --- Alerts ---------------------------------------------------------------


@freeze_time(FROZEN_NOW)
def test_alerts_requires_admin_or_coord(client, vacation_old_user):
    response = client.get(
        ENDPOINT_URL + '/alerts',
        headers=auth_headers(client, vacation_old_user),
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@freeze_time(FROZEN_NOW)
def test_expired_alerts(client, vacation_old_user, vacation_admin):
    client.get(
        ENDPOINT_URL + '/accrual-periods',
        headers=auth_headers(client, vacation_old_user),
    )
    response = client.get(
        ENDPOINT_URL + '/alerts',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    alerts = response.json()
    expired = [a for a in alerts if a['alert_type'] == 'expired']
    assert len(expired) == EXPIRED_PERIODS_COUNT
    assert all(
        alert['remaining_days'] == VACATION_YEAR_DAYS for alert in expired
    )
    assert all('concessive_start' in alert for alert in alerts)


@freeze_time(FROZEN_NOW)
def test_pending_alert_for_open_concessive_without_schedule(
    client, vacation_user, vacation_admin
):
    client.get(
        ENDPOINT_URL + '/accrual-periods',
        headers=auth_headers(client, vacation_user),
    )
    response = client.get(
        ENDPOINT_URL + '/alerts',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    alerts = response.json()
    user_alerts = [
        alert for alert in alerts if alert['user_id'] == vacation_user.id
    ]
    assert len(user_alerts) == 1
    alert = user_alerts[0]
    assert alert['alert_type'] == 'pending'
    assert alert['remaining_days'] == VACATION_YEAR_DAYS


@freeze_time(FROZEN_NOW)
def test_about_to_expire_alert(client, about_to_expire_user, vacation_admin):
    client.get(
        ENDPOINT_URL + '/accrual-periods',
        headers=auth_headers(client, about_to_expire_user),
    )
    response = client.get(
        ENDPOINT_URL + '/alerts',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    alerts = response.json()
    user_alerts = [
        alert
        for alert in alerts
        if alert['user_id'] == about_to_expire_user.id
    ]
    assert len(user_alerts) == 1
    assert user_alerts[0]['alert_type'] == 'about_to_expire'


@freeze_time(FROZEN_NOW)
def test_alert_appears_for_user_without_prior_interaction(
    client, vacation_old_user, vacation_admin
):
    """Usuário que nunca acessou o módulo deve aparecer nos alertas."""
    response = client.get(
        ENDPOINT_URL + '/alerts',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    alerts = response.json()
    user_alerts = [
        alert for alert in alerts if alert['user_id'] == vacation_old_user.id
    ]
    assert user_alerts, (
        'Usuário sem interação prévia deve aparecer nos alertas'
    )
    assert any(alert['alert_type'] == 'expired' for alert in user_alerts)


@freeze_time(FROZEN_NOW)
def test_no_alert_when_request_pending(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    create_request(client, headers, [MAIN_PERIOD], period['id'])

    response = client.get(
        ENDPOINT_URL + '/alerts',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    alerts = response.json()
    user_alerts = [
        alert for alert in alerts if alert['user_id'] == vacation_user.id
    ]
    assert user_alerts == []


@freeze_time(FROZEN_NOW)
def test_no_alert_when_grant_active(client, vacation_user, vacation_admin):
    headers = auth_headers(client, vacation_user)
    period = get_period_by_status(client, headers, 'concessive')
    request_id = create_request(client, headers, [MAIN_PERIOD], period['id'])

    response = client.post(
        f'{ENDPOINT_URL}/requests/{request_id}/approve',
        headers=auth_headers(client, vacation_admin),
        json={},
    )
    assert response.status_code == HTTPStatus.OK

    response = client.get(
        ENDPOINT_URL + '/alerts',
        headers=auth_headers(client, vacation_admin),
    )
    assert response.status_code == HTTPStatus.OK
    alerts = response.json()
    user_alerts = [
        alert for alert in alerts if alert['user_id'] == vacation_user.id
    ]
    assert user_alerts == []


# --- Filtro por setor/subsetor -------------------------------------------


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_list_grants_by_sector(client, session, vacation_admin):
    registro_user = build_user(
        role=Role.USER, setor=Setor.REGISTRO, subsetor='Análise'
    )
    admin_user = build_user(
        role=Role.USER, setor=Setor.ADMINISTRATIVO, subsetor='Atendimento'
    )
    session.add_all([registro_user, admin_user])
    await session.commit()  # type: ignore[misc]

    admin_headers = auth_headers(client, vacation_admin)
    grant_ids = {}
    for user in (registro_user, admin_user):
        headers = auth_headers(client, user)
        period = get_period_by_status(client, headers, 'concessive')
        request_id = create_request(
            client, headers, [MAIN_PERIOD], period['id']
        )
        response = client.post(
            f'{ENDPOINT_URL}/requests/{request_id}/approve',
            headers=admin_headers,
            json={},
        )
        assert response.status_code == HTTPStatus.OK
        grant = client.get(ENDPOINT_URL + '/grants', headers=headers).json()[0]
        grant_ids[user.id] = grant['id']

    response = client.get(
        ENDPOINT_URL + '/grants/by-sector/registro',
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.OK
    items = response.json()
    assert [g['id'] for g in items] == [grant_ids[registro_user.id]]

    response = client.get(
        ENDPOINT_URL + '/grants/by-sector/administrativo',
        headers=admin_headers,
    )
    assert [g['id'] for g in response.json()] == [grant_ids[admin_user.id]]


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_list_grants_by_sector_and_subsetor(
    client, session, vacation_admin
):
    subsetor = 'Atendimento'
    admin_user = build_user(
        role=Role.USER, setor=Setor.ADMINISTRATIVO, subsetor=subsetor
    )
    other_admin_user = build_user(
        role=Role.USER, setor=Setor.ADMINISTRATIVO, subsetor='Apoio'
    )
    session.add_all([admin_user, other_admin_user])
    await session.commit()  # type: ignore[misc]

    admin_headers = auth_headers(client, vacation_admin)
    target_ids = {}
    for user in (admin_user, other_admin_user):
        headers = auth_headers(client, user)
        period = get_period_by_status(client, headers, 'concessive')
        request_id = create_request(
            client, headers, [MAIN_PERIOD], period['id']
        )
        response = client.post(
            f'{ENDPOINT_URL}/requests/{request_id}/approve',
            headers=admin_headers,
            json={},
        )
        assert response.status_code == HTTPStatus.OK
        grant = client.get(ENDPOINT_URL + '/grants', headers=headers).json()[0]
        target_ids[user.id] = grant['id']

    response = client.get(
        f'{ENDPOINT_URL}/grants/by-sector/administrativo?subsetor={subsetor}',
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.OK
    items = response.json()
    assert [g['id'] for g in items] == [target_ids[admin_user.id]]


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_list_requests_by_sector(client, session, vacation_admin):
    registro_user = build_user(
        role=Role.USER, setor=Setor.REGISTRO, subsetor='Análise'
    )
    admin_user = build_user(
        role=Role.USER, setor=Setor.ADMINISTRATIVO, subsetor='Atendimento'
    )
    session.add_all([registro_user, admin_user])
    await session.commit()  # type: ignore[misc]

    admin_headers = auth_headers(client, vacation_admin)
    expected_ids = {}
    for user in (registro_user, admin_user):
        headers = auth_headers(client, user)
        period = get_period_by_status(client, headers, 'concessive')
        expected_ids[user.id] = create_request(
            client, headers, [MAIN_PERIOD], period['id']
        )

    response = client.get(
        ENDPOINT_URL + '/requests/by-sector/registro',
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.OK
    items = response.json()
    assert [r['id'] for r in items] == [expected_ids[registro_user.id]]

    response = client.get(
        ENDPOINT_URL + '/requests/by-sector/administrativo?subsetor=Apoio',
        headers=admin_headers,
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


@pytest.mark.asyncio
@freeze_time(FROZEN_NOW)
async def test_list_grants_by_sector_requires_admin_or_coord(
    client, session, vacation_user
):
    headers = auth_headers(client, vacation_user)
    response = client.get(
        ENDPOINT_URL + '/grants/by-sector/registro',
        headers=headers,
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
