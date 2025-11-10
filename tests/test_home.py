from http import HTTPStatus


def test_get_home_summary_data(client, token):
    response = client.get(
        'api/v1/home',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
