import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "anand")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "lms_db")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
