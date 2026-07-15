from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Ally Backend API"
    VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"


settings = Settings()