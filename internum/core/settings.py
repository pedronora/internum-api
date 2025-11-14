from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env.development', env_file_encoding='utf-8'
    )

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_DB: str
    POSTGRES_PASSWORD: str
    DATABASE_URL: str = ''
    REFRESH_COOKIE_NAME: str
    REFRESH_COOKIE_PATH: str
    REFRESH_TOKEN_EXPIRE_DAYS: int
    REFRESH_COOKIE_MAX_AGE: int
    SECURE_COOKIE: bool
    REFRESH_COOKIE_SAMESITE: str
    ADMIN_NAME: str
    ADMIN_USERNAME: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    MAILTRAP_TOKEN: str

    def __init__(self, **values):
        super().__init__(**values)
        self.DATABASE_URL = f'postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}'
