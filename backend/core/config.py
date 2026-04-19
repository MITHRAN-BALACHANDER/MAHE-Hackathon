from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Cellular Maze API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # External Services
    MODEL_URL: str = "http://localhost:8001"
    OSRM_URL: str = "http://router.project-osrm.org"

    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "cellularmaze"

    # Timeouts
    ML_TIMEOUT_S: float = 5.0
    OSRM_TIMEOUT_S: float = 10.0

    # Cache
    SIGNAL_CACHE_TTL_S: int = 300
    SIGNAL_CACHE_MAX_SIZE: int = 10_000

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
