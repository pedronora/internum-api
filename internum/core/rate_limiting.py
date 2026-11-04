from fastapi import Request
from slowapi import Limiter

from internum.core.settings import Settings

settings = Settings()


def client_identifier(request: Request) -> str:
    """Identifica o cliente para o rate limit.

    O nginx do frontend sobrescreve `X-Real-IP` e `X-Forwarded-For` com o
    endereço real, então esses headers são confiáveis quando a API só é
    acessível através do proxy. O bind da API não deve ser publicado.
    """
    real_ip = request.headers.get('x-real-ip')
    if real_ip:
        return real_ip.strip()

    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()

    if request.client:
        return request.client.host

    return 'desconhecido'


limiter = Limiter(
    key_func=client_identifier,
    headers_enabled=True,
    enabled=settings.RATE_LIMIT_ENABLED,
)
