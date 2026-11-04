import os

# Os testes do suite desabilitam o rate limit; o teste dedicado o habilita
# explicitamente. Precisa acontecer antes de importar `internum.core.settings`.
os.environ.setdefault('RATE_LIMIT_ENABLED', 'false')
