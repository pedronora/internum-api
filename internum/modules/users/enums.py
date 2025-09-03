from enum import Enum


class Role(str, Enum):
    ADMIN = 'admin'
    COORD = 'coord'
    USER = 'user'


class Setor(str, Enum):
    REGISTRO = 'registro'
    ADMINISTRATIVO = 'administrativo'
    OFICIAL = 'oficial'


SUBSETORES_POR_SETOR = {
    Setor.REGISTRO: [
        'Análise',
        'Conferência',
        'Finalização/Impressão',
        'Busca e Certidão',
        'Arquivo',
    ],
    Setor.ADMINISTRATIVO: ['Atendimento', 'Digitalização', 'Apoio'],
    Setor.OFICIAL: ['Titular', 'Substituto'],
}
