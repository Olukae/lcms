import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_COOKIE_NAME = "lcms_access_token"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_ACCESS_CSRF_COOKIE_NAME = "lcms_csrf_token"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_COOKIE_SAMESITE = "Strict"
    JWT_COOKIE_SECURE = os.environ.get("JWT_COOKIE_SECURE", "false").lower() == "true"

    # Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER") or None
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or None
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD") or None
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "lcms@lasu.edu.ng")
    MAIL_SUPPRESS_SEND = MAIL_SERVER is None

    WTF_CSRF_ENABLED = True

    PASSWORD_RESET_EXPIRY_MINUTES = 30
    BCRYPT_LOG_ROUNDS = 12


class DevConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'lcms_dev.db')}"
    )


class TestConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    JWT_COOKIE_CSRF_PROTECT = False
    BCRYPT_LOG_ROUNDS = 4  # faster tests


class ProdConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://lcms_user:password@localhost:3306/lcms_db",
    )
    JWT_COOKIE_SECURE = True


config_map = {
    "development": DevConfig,
    "testing": TestConfig,
    "production": ProdConfig,
    "default": DevConfig,
}
