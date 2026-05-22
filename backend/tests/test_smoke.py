"""Smoke test to verify pytest + uv + project layout are wired up."""

from app.infra.config import Settings


def test_settings_loads_with_defaults():
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.default_batch_size == 3
    assert settings.default_batch_window_minutes == 30
