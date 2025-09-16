from jwt import decode

from internum.core.security import SECRET_KEY, create_access_token


def test_jwt():
    data = {'teste': 'teste'}
    token = create_access_token(data)

    decoded = decode(token, SECRET_KEY, algorithms=['HS256'])

    assert decoded['teste'] == data['teste']
    assert 'exp' in decoded
