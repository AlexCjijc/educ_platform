import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    # SQLite (по умолчанию)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///stepikish.db"  # для MySQL: "mysql://user:pass@localhost/stepikish?charset=utf8mb4"
    )
    UPLOAD_COURSE_DIR = os.environ.get('UPLOAD_COURSE_DIR', 'uploads/courses')  # внутри static/
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    UPLOAD_AVATAR_DIR = os.environ.get('UPLOAD_AVATAR_DIR', 'uploads/avatars')  # внутри static/
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Ограничения курса по умолчанию
    DEFAULT_MAX_ATTEMPTS = 3
