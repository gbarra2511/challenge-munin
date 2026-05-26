from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://munin:munin@localhost:5432/munin"

    jwt_secret: str = "dev-only-change-me"
    jwt_expires_minutes: int = 720

    tick_secret: str = "dev-only-change-me-tick"
    admin_secret: str = "dev-only-change-me-admin"

    default_batch_size: int = 3
    default_batch_window_minutes: int = 30
    default_escalate_hours_before: int = 6

    cors_origins: str = "http://localhost:3000"

    # Base pública do frontend — usada para montar deep links nas notificações.
    frontend_url: str = "http://localhost:3000"

    # WhatsApp via Twilio. Sem estas credenciais, o NullNotifier assume
    # (loga e não envia) — dev/test nunca tocam a rede.
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None  # ex.: "whatsapp:+14155238886" (sandbox)

    # Celular (opt-in no sandbox) que recebe as notificações reais da demo:
    # coordenadora e médico-demo apontam para ele. Lido pelo seed.
    munin_demo_phone: str | None = None

    resend_api_key: str | None = None
    anthropic_api_key: str | None = None


def get_settings() -> Settings:
    return Settings()
