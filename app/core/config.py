"""Application configuration.

Every setting can be overridden with an environment variable prefixed with ``APP_``
or with a value in a local ``.env`` file. For example ``APP_MAX_RETRIES=5`` sets
``max_retries`` to 5.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repository root is two levels above this file: app/core/config.py -> app/ -> root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the whole application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Web Scraping & Data Extraction Platform"
    app_version: str = "0.3.0"
    environment: str = "development"
    log_level: str = "INFO"

    # Networking. The user agent identifies the crawler so site owners can contact us.
    user_agent: str = (
        "Mozilla/5.0 (compatible; WebScrapingDataPlatform/0.1; "
        "+https://github.com/CtrlAltDev-wq/web-scraping-data-platform)"
    )
    request_timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    request_delay_seconds: float = 0.5
    respect_robots_txt: bool = True

    # Scraping defaults.
    default_max_pages: int = 3
    max_pages_limit: int = 20

    # Browser rendering. Used only by sources that declare ``requires_browser``.
    browser_headless: bool = True
    browser_timeout_ms: int = 30_000

    # Storage. Raw HTML, run outputs and future exports all live under ``data``.
    data_dir: Path = PROJECT_ROOT / "data"
    # Leave empty to use the SQLite file under ``data_dir``.
    database_url: str | None = None

    @property
    def raw_dir(self) -> Path:
        """Directory holding the original HTML of every fetched page."""
        return self.data_dir / "raw"

    @property
    def runs_dir(self) -> Path:
        """Directory holding one sub-directory per scrape run."""
        return self.data_dir / "runs"

    @property
    def exports_dir(self) -> Path:
        """Directory for generated CSV / Excel files."""
        return self.data_dir / "exports"

    @property
    def screenshots_dir(self) -> Path:
        """Directory holding browser screenshots captured as scraping evidence."""
        return self.data_dir / "screenshots"

    @property
    def db_path(self) -> Path:
        """Default SQLite database file."""
        return self.data_dir / "scraped.db"

    @property
    def resolved_database_url(self) -> str:
        """Database URL, defaulting to SQLite inside ``data_dir``."""
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.db_path.as_posix()}"

    def ensure_directories(self) -> None:
        """Create the storage directories if they do not exist yet."""
        for directory in (self.raw_dir, self.runs_dir, self.exports_dir, self.screenshots_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached across calls)."""
    return Settings()
