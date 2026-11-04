from enum import Enum


class Unidade(str, Enum):
    DIRECAO = 'direcao'
    REGISTRO = 'registro'
    GESTAO = 'gestao'


class Role(str, Enum):
    OFICIAL = 'oficial'
    SUBOFICIAL = 'suboficial'
    COORD_REGISTRO = 'coord_registro'
    COORD_GESTAO = 'coord_gestao'
    GESTOR_PESSOAS = 'gestor_pessoas'
    COLABORADOR_REGISTRO = 'colaborador_registro'
    COLABORADOR_GESTAO = 'colaborador_gestao'


# Sugestões de lotação. `subunidade` é texto livre: a lista existe apenas
# para orientar o cadastro e nunca concede permissão.
SUBUNIDADES_SUGERIDAS = [
    'Atendimento',
    'Digitalização',
    'Pessoas',
    'Financeiro',
    'Compras/Patrimônio',
    'TI',
]
