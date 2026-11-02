"""Central configuration, loaded from environment variables (see .env.example)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- Core -----------------------------------------------------------
    app_name: str = "Heatmapify"
    redis_url: str = "redis://localhost:6379/0"
    public_base_url: str = ""  # e.g. https://api.example.com (used to build status_url)
    log_level: str = "INFO"
    cors_origins: str = ""  # comma-separated, "*" for any, empty = CORS disabled
    # Browser pages on this computer (a dashboard opened from localhost) are allowed as well.
    cors_allow_localhost: bool = True

    # --- Auth / limits ---------------------------------------------------
    require_api_key: bool = True
    api_key_pepper: str = "change-me"  # HMAC secret used when hashing keys
    api_key_hashes: str = ""  # optional static keys: comma-separated HMAC-SHA256 hex digests
    default_rate_limit_per_min: int = 30
    default_daily_quota: int = 500

    # --- Cache / jobs ----------------------------------------------------
    cache_ttl_official: int = 24 * 3600
    cache_ttl_estimated: int = 7 * 24 * 3600
    job_result_ttl: int = 24 * 3600
    job_timeout: int = 900
    official_timeout: float = 25.0
    worker_concurrency: int = 2  # worker processes per worker container
    global_max_jobs: int = 4  # cluster-wide cap on simultaneous heavy jobs (Redis semaphore)
    tmp_dir: str = "/tmp/yt-heatmap"

    # --- Processing ------------------------------------------------------
    max_estimate_duration: int = 3600  # seconds; estimated mode only
    window_seconds: int = 10
    min_window_seconds: int = 5
    max_window_seconds: int = 60
    max_top: int = 20
    merge_tolerance: float = 0.05

    weight_comments: float = 0.35
    weight_transcript: float = 0.25
    weight_audio: float = 0.25
    weight_visual: float = 0.15
    # Estimates are reshaped so the median segment scores this (YouTube's own data is mostly
    # near zero with sharp spikes). 0 = keep the plain weighted average.
    estimate_median_target: float = 0.12

    enable_comments: bool = True
    enable_transcript: bool = True
    enable_audio: bool = True
    enable_visual: bool = True
    # YAMNet audio events (laughter, applause, crowd). Off = loudness-only audio signal.
    audio_events: bool = True

    min_timestamped_comments: int = 10
    comment_spread_seconds: float = 5.0
    max_comments: int = 2000
    visual_max_height: int = 360

    # --- YouTube access ---------------------------------------------------
    yt_proxy: str = ""
    yt_cookies_file: str = ""
    yt_api_key: str = ""  # YouTube Data API v3 key (optional, for comments)
    yt_api_daily_quota: int = 10000
    retry_attempts: int = 3
    retry_backoff: float = 2.0

    # --- Optional LLM pass on transcript (OpenAI-compatible) --------------
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_blend: float = Field(0.5, ge=0, le=1)

    # --- Webhooks --------------------------------------------------------
    allow_webhooks: bool = True
    webhook_timeout: float = 10.0

    @property
    def weights(self) -> dict[str, float]:
        return {
            "comments": self.weight_comments,
            "transcript": self.weight_transcript,
            "audio": self.weight_audio,
            "visual": self.weight_visual,
        }

    @property
    def enabled_signals(self) -> dict[str, bool]:
        return {
            "comments": self.enable_comments,
            "transcript": self.enable_transcript,
            "audio": self.enable_audio,
            "visual": self.enable_visual,
        }

    @property
    def cors_localhost_regex(self) -> str | None:
        return r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$" if self.cors_allow_localhost else None

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
