
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    api_title: str = "Logistics & Route Aggregator API"
    api_version: str = "1.0.0"
    owm_api_key: str = "" # Loaded from .env
    owm_base_url: str = "https://api.openweathermap.org/data/2.5/weather"
    api_key: str 

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()