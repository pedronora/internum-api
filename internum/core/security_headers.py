from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_DOCS_PATHS = frozenset({
    '/docs',
    '/redoc',
    '/openapi.json',
    '/docs/oauth2-redirect',
})

_API_CSP = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'none'"
)


class SecurityHeadersMiddleware:
    """Adiciona headers de segurança em todas as respostas da API.

    A API só devolve JSON, então a CSP pode ser restritiva. As páginas de
    documentação interativa ficam de fora da CSP porque carregam assets
    externos; elas só existem quando `DOCS_ENABLED=True`.
    """

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        is_docs = scope['path'] in _DOCS_PATHS

        async def send_with_headers(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                headers.setdefault('X-Content-Type-Options', 'nosniff')
                headers.setdefault('X-Frame-Options', 'DENY')
                headers.setdefault('Referrer-Policy', 'no-referrer')
                headers.setdefault(
                    'Permissions-Policy',
                    'camera=(), microphone=(), geolocation=()',
                )
                headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
                headers.setdefault('Cross-Origin-Resource-Policy', 'same-site')

                if not is_docs:
                    headers.setdefault('Content-Security-Policy', _API_CSP)

                if self.hsts:
                    headers.setdefault(
                        'Strict-Transport-Security',
                        'max-age=31536000; includeSubDomains',
                    )

            await send(message)

        await self.app(scope, receive, send_with_headers)
