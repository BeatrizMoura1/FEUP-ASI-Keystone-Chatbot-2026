from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECTS = ["GENERAL", "A", "B"]
NO_ANSWER_TEXT = "No answer found."


class Settings(BaseSettings):
    """Application settings loaded from the environment and the local .env file.

    Settings are organised into the following groups:

    1. **LLM** - provider choice, Gemini key/model, Ollama URL/model, retry behaviour, chat history length.
    2. **Storage** - SQLite database path and the folder of seed documents.
    """

    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="", alias="GEMINI_MODEL")
    ollama_url: str = Field(default="http://localhost:11434", alias="OLLAMA_URL")
    ollama_model: str = Field(default="", alias="OLLAMA_MODEL")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")
    llm_retry_wait_seconds: float = Field(default=3.0, alias="LLM_RETRY_WAIT_SECONDS")
    chat_history_messages: int = Field(
        default=6,
        alias="CHAT_HISTORY_MESSAGES",
        description="How many earlier messages of the chat are sent with each question (0 disables follow-ups).",
    )

    database_path: str = Field(default="knowledge_finder.db", alias="DATABASE_PATH")
    docs_dir: str = Field(default=".docs", alias="DOCS_DIR")

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _validate_provider(cls, raw_provider: object) -> str:
        """Normalise the provider name and reject unknown providers at startup.

        Parameters
        ----------
        raw_provider : object
            Raw LLM_PROVIDER value.

        Returns
        -------
        str
            Lower-case provider name.

        Raises
        ------
        ValueError
            If the provider is not "gemini" or "ollama".
        """
        provider_name = str(raw_provider).strip().lower()
        if provider_name not in {"gemini", "ollama"}:
            raise ValueError(f"LLM_PROVIDER must be 'gemini' or 'ollama', got '{provider_name}'")
        return provider_name

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
