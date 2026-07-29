from __future__ import annotations

from typing import List, Optional
from pydantic import Field, AnyUrl

# BaseSettings moved to pydantic-settings in newer Pydantic versions;
# support both by trying pydantic_settings first and falling back.
try:
    from pydantic_settings import BaseSettings
except Exception:
    try:
        from pydantic import BaseSettings  # type: ignore
    except Exception:
        # Pydantic v2 may move BaseSettings to pydantic-settings; when unavailable,
        # fall back to using BaseModel as a safe approximation for config models.
        from pydantic import BaseModel as BaseSettings  # type: ignore

# field_validator is new in Pydantic v2. Provide a compatibility shim
# that maps v2's field_validator(mode="before") to v1's validator(pre=True).
try:
    from pydantic import field_validator as _field_validator
    field_validator = _field_validator
except Exception:
    from pydantic import validator as _validator

    def field_validator(*fields, mode=None, **kwargs):
        pre = True if mode == "before" else False

        def _decorator(func):
            return _validator(*fields, pre=pre, **kwargs)(func)

        return _decorator


class LoggingConfig(BaseSettings):
    level: str = Field("INFO")
    console: bool = Field(True)
    file: bool = Field(True)
    file_path: str = Field("phase9/logs/phase9.log")
    max_bytes: int = Field(10 * 1024 * 1024)
    backup_count: int = Field(5)


class OutputConfig(BaseSettings):
    artifacts_root: str = Field("artifacts/phase9/latest")
    staging_dir: str = Field("phase9/packaging/staging")


class DiscoveryConfig(BaseSettings):
    phases: List[int] = Field([2, 3, 4, 5, 6, 7, 8])
    manifest_filename: str = Field("manifest.json")


class FeaturesConfig(BaseSettings):
    enable_figure_generation: bool = Field(True)
    include_optional_artifacts: bool = Field(False)


class PoliciesConfig(BaseSettings):
    duplicate_resolution: str = Field("prefer-manifest")


class Phase9Settings(BaseSettings):
    output: OutputConfig = Field(default_factory=OutputConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    policies: PoliciesConfig = Field(default_factory=PoliciesConfig)

    model_config = {"env_prefix": "PHASE9_", "arbitrary_types_allowed": True}

    @field_validator("output", mode="before")
    def _resolve_paths(cls, v):
        # Accept dict or OutputConfig
        return v


__all__ = ["Phase9Settings", "OutputConfig", "DiscoveryConfig", "LoggingConfig", "FeaturesConfig", "PoliciesConfig"]
