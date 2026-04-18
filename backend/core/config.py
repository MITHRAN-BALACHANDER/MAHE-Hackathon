from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "SignalRoute API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # External Services
    ML_MODEL_URL: str
    OSRM_URL: str
    
    # DB
    DATABASE_URL: str

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
