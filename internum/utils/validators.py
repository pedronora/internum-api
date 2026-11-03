MIN_LENGTH_PWD = 8
MAX_LENGTH_PWD = 64


def validate_password_complexity(pwd: str) -> str:
    if len(pwd) < MIN_LENGTH_PWD or len(pwd) > MAX_LENGTH_PWD:
        raise ValueError('A senha deve ter entre 8 e 64 caracteres.')
    if not any(char.isdigit() for char in pwd):
        raise ValueError('A senha deve conter pelo menos um dígito.')
    if not any(char.islower() for char in pwd):
        raise ValueError('A senha deve conter pelo menos uma letra minúscula.')
    if not any(char.isupper() for char in pwd):
        raise ValueError('A senha deve conter pelo menos uma letra maiúscula.')
    if not any(not char.isalnum() for char in pwd):
        raise ValueError(
            'A senha deve conter pelo menos um caractere especial.'
        )
    return pwd
