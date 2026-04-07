from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ------------------------------------------------------------------------------
# Sub-settings — each service has its own config block.
# This keeps access clean: settings.mongo.url, settings.redis.url, etc.
# ------------------------------------------------------------------------------

class AppSettings(BaseSettings):
    env: str = Field("staging", alias="APP_ENV")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class MongoSettings(BaseSettings):
    url: str = Field("mongodb://localhost:27017", alias="MONGO_URL")        # replace with your actual value
    db_name: str = Field("multi_booking_agent", alias="MONGO_DB_NAME")     # replace with your actual value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class RedisSettings(BaseSettings):
    url: str = Field("redis://localhost:6379", alias="REDIS_URL")           # replace with your actual value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class OpenAISettings(BaseSettings):
    api_key: str = Field("", alias="OPENAI_API_KEY")                        # replace with your actual value
    model: str = Field("gpt-4o", alias="CHATGPT_MODEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Mem0Settings(BaseSettings):
    api_key: str = Field("", alias="MEM0_API_KEY")                          # replace with your actual value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class StripeSettings(BaseSettings):
    secret_key: str = Field("", alias="STRIPE_SECRET_KEY")                  # replace with your actual value
    publish_secret_key: str = Field("", alias="STRIPE_PUBLISH_SECRET_KEY")  # replace with your actual value
    webhook_secret_key: str = Field("", alias="STRIPE_WEBHOOK_SECRET_KEY")  # replace with your actual value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class TwilioSettings(BaseSettings):
    auth_token: str = Field("", alias="TWILIO_AUTH_TOKEN")                  # replace with your actual value
    account_sid: str = Field("", alias="TWILIO_ACCOUNT_SID")               # replace with your actual value
    phone_number: str = Field("", alias="TWILIO_PHONE_NUMBER")             # replace with your actual value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class JWTSettings(BaseSettings):
    secret_key: str = Field("", alias="JWT_SECRET_KEY")                     # replace with your actual value
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# ------------------------------------------------------------------------------
# Root settings — composes all sub-settings into a single object.
# Usage anywhere in the project:
#   from config import get_settings
#   settings = get_settings()
#   settings.mongo.url
# ------------------------------------------------------------------------------

class Settings:
    def __init__(self) -> None:
        self.app    = AppSettings()
        self.mongo  = MongoSettings()
        self.redis  = RedisSettings()
        self.openai = OpenAISettings()
        self.mem0   = Mem0Settings()
        self.stripe = StripeSettings()
        self.twilio = TwilioSettings()
        self.jwt    = JWTSettings()


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    The cache ensures .env is parsed only once for the entire process lifetime.
    """
    return Settings()
