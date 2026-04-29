from http import HTTPStatus

from jwt import decode

from pizzaria_system.security import create_access_token
from pizzaria_system.settings import Settings

settings = Settings()


def test_jwt():
    data = {'sub': 'test@example.com'}
    token = create_access_token(data)
    result = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert result['sub'] == data['sub']
    assert result['exp']


def test_jwt_invalid_token(client):
    response = client.delete('/clientes/1', headers={'Authorization': 'Bearer token-invalido'})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}