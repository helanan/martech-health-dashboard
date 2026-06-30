from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "martech_vault"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl_seconds: int = 300

    # Elasticsearch / OpenSearch
    es_hosts: str = "http://localhost:9200"  # single host string; split on comma in client
    es_api_key: str = ""
    es_index_prefix: str = "martech"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "info"


settings = Settings()
