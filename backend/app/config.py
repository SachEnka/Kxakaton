from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://credit:credit@localhost:5432/credit"
    jwt_secret: str = "demo-secret-change-me"
    jwt_ttl_minutes: int = 60 * 12
    demo_password: str = "Demo-2026"


settings = Settings()
