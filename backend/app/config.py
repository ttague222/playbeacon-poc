from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Firebase
    firebase_credentials_path: str = "serviceAccountKey.json"
    firebase_project_id: Optional[str] = None

    # OpenAI
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Pinecone
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    pinecone_index_name: str = "roblox-games"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # LLM
    llm_model: str = "gpt-3.5-turbo"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
