from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECTS = {
    "GENERAL": "General (everyone)",
    "A": "Project A: Linha Verde Metro Extension",
    "B": "Project B: Offshore Wind Tender",
}
NO_ANSWER_TEXT = "No answer found."


class Settings(BaseSettings):
    """Application settings loaded from the environment and the local .env file.

    Settings are organised into the following groups:

    1. **LLM** - Gemini key/model, retry behaviour, chat history length.
    2. **Storage** - PostgreSQL connection strings and the folder of seed documents.
    3. **Test accounts** - passwords of the employee, newhire and admin accounts created by `db/reset.py`.
    """

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="", alias="GEMINI_MODEL")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")
    llm_retry_wait_seconds: float = Field(default=3.0, alias="LLM_RETRY_WAIT_SECONDS")
    chat_history_messages: int = Field(
        default=6,
        alias="CHAT_HISTORY_MESSAGES",
        description="How many earlier messages of the chat are sent with each question (0 disables follow-ups).",
    )

    docs_dir: str = Field(default="sample_documents", alias="DOCS_DIR")
    database_url: str = Field(
        default="postgresql://localhost/keystone",
        alias="DATABASE_URL",
        description="PostgreSQL connection string (Neon in production, local PostgreSQL in development).",
    )
    test_database_url: str = Field(
        default="postgresql://localhost/keystone_test",
        alias="TEST_DATABASE_URL",
        description="Local PostgreSQL database the tests use; its data is wiped on every test.",
    )

    employee_password: str = Field(default="", alias="EMPLOYEE_PASSWORD")
    newhire_password: str = Field(default="", alias="NEWHIRE_PASSWORD")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
