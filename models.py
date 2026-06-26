from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()

# Роли на уровне сайта
class SiteRole:
    OWNER = "OWNER"        # создатель платформы
    ADMIN = "ADMIN"        # админ сайта
    MODERATOR = "MODERATOR"  # модератор
    USER = "USER"          # обычный пользователь

# Роли внутри курса
class CourseRole:
    CREATOR = "CREATOR"
    TEACHER = "TEACHER"
    EDITOR = "EDITOR"
    STUDENT = "STUDENT"

# Приватность курса
class CourseVisibility:
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"   # по ссылке/приглашению или ID

# Тип вопроса
class QuestionType:
    SINGLE = "SINGLE"     # один вариант
    MULTI = "MULTI"       # несколько вариантов
    ORDER = "ORDER"       # порядок
    MATCH = "MATCH"       # соответствие (MVP пропустим реал)
    TEXT = "TEXT"         # развёрнутый ответ

# Уведомления
class NotificationType:
    GRADE_PUBLISHED = "GRADE_PUBLISHED"
    NEED_GRADING = "NEED_GRADING"
    CHAT_MENTION = "CHAT_MENTION"

# Чаты
class ChatType:
    COURSE_PUBLIC = "COURSE_PUBLIC"
    COURSE_STAFF = "COURSE_STAFF"
    DM = "DM"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    site_role = db.Column(db.String(32), default=SiteRole.USER, nullable=False)
    rating = db.Column(db.Float, default=0.0)  # рейтинг профиля
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    avatar_path = db.Column(db.String(256), nullable=True)  # относительный путь в static/
    bio = db.Column(db.Text, nullable=True)
    # связи
    courses_created = db.relationship("Course", backref="creator", lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    category = db.Column(db.String(64), nullable=True)
    image_path = db.Column(db.String(256), nullable=True)

    visibility = db.Column(db.String(16), default=CourseVisibility.PUBLIC, nullable=False)
    invite_token = db.Column(db.String(64), nullable=True)  # для приватных
    max_students = db.Column(db.Integer, nullable=True)     # None = без ограничений

    access_start = db.Column(db.DateTime, nullable=True)
    access_end = db.Column(db.DateTime, nullable=True)

    require_sequence = db.Column(db.Boolean, default=True)  # последовательность прохождения
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # рейтинги/отзывы
    rating = db.Column(db.Float, default=0.0)
    reviews_count = db.Column(db.Integer, default=0)

class CourseRoleMap(db.Model):
    __tablename__ = "course_role_map"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role = db.Column(db.String(32), default=CourseRole.STUDENT, nullable=False)

    user = db.relationship("User")
    course = db.relationship("Course")

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    order_idx = db.Column(db.Integer, default=0)

    course = db.relationship("Course", backref=db.backref("chapters", cascade="all, delete-orphan"))

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    html_content = db.Column(db.Text, nullable=False)   # редактор (жирный, курсив и т. п.)
    order_idx = db.Column(db.Integer, default=0)
    video_url = db.Column(db.String(512), nullable=True)   # YouTube/Rutube
    external_files = db.Column(db.Text, nullable=True)     # ссылки на облако

    chapter = db.relationship("Chapter", backref=db.backref("lessons", cascade="all, delete-orphan"))
    code_panel_enabled = db.Column(db.Boolean, default=False)
    code_language = db.Column(db.String(16), nullable=True)


class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=True)  # НОВОЕ
    title = db.Column(db.String(256), nullable=False)
    time_limit_sec = db.Column(db.Integer, nullable=True)
    max_attempts = db.Column(db.Integer, nullable=True)
    auto_grade = db.Column(db.Boolean, default=True)
    order_idx = db.Column(db.Integer, default=0)                                     # НОВОЕ

    chapter = db.relationship("Chapter", backref=db.backref("tests", cascade="all, delete-orphan"))
    section = db.relationship("Section", backref=db.backref("tests", cascade="all, delete-orphan"))

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("test.id"), nullable=False)
    qtype = db.Column(db.String(16), default=QuestionType.SINGLE, nullable=False)
    text = db.Column(db.Text, nullable=False)
    order_idx = db.Column(db.Integer, default=0)
    points = db.Column(db.Float, default=1.0)

    test = db.relationship("Test", backref=db.backref("questions", cascade="all, delete-orphan"))

class AnswerOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    text = db.Column(db.String(512), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order_idx = db.Column(db.Integer, default=0)

    question = db.relationship("Question", backref=db.backref("options", cascade="all, delete-orphan"))

# Задания с ответом (текст или файл — MVP: текст)
class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=True)  # НОВОЕ
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=False)
    time_limit_sec = db.Column(db.Integer, nullable=True)
    max_attempts = db.Column(db.Integer, nullable=True)
    auto_grade = db.Column(db.Boolean, default=False)
    order_idx = db.Column(db.Integer, default=0)                                     # НОВОЕ

    chapter = db.relationship("Chapter", backref=db.backref("assignments", cascade="all, delete-orphan"))
    section = db.relationship("Section", backref=db.backref("assignments", cascade="all, delete-orphan"))

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    progress_pct = db.Column(db.Float, default=0.0)
    quality_score = db.Column(db.Float, default=0.0)  # «качество обучения» — агрегат оценок

    user = db.relationship("User")
    course = db.relationship("Course")

class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)

class TestAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("test.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Float, default=0.0)
    max_score = db.Column(db.Float, default=0.0)
    graded = db.Column(db.Boolean, default=False)
    manual_required = db.Column(db.Boolean, default=False)  # если есть TEXT вопросы

class TestAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("test_attempt.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    selected_option_ids = db.Column(db.String(512), nullable=True)  # CSV для MULTI/ORDER
    text_answer = db.Column(db.Text, nullable=True)

class AssignmentSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignment.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    text_answer = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, default=0.0)
    max_score = db.Column(db.Float, default=0.0)
    graded = db.Column(db.Boolean, default=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewer_comment = db.Column(db.Text, nullable=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1..5
    text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    ntype = db.Column(db.String(32), nullable=False)
    payload = db.Column(db.Text, nullable=True)  # JSON-строка с метаданными
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=True)
    ctype = db.Column(db.String(32), default=ChatType.COURSE_PUBLIC, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_enabled = db.Column(db.Boolean, default=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chat.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    mentions = db.Column(db.String(512), nullable=True)  # CSV user_ids для упоминаний

    chat = db.relationship("Chat", backref=db.backref("messages", cascade="all, delete-orphan"))

# Подглава (Section / Subchapter)
class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    order_idx = db.Column(db.Integer, default=0)

    chapter = db.relationship("Chapter", backref=db.backref("sections", cascade="all, delete-orphan"))

# В Course — флаги и ограничения
Course.public_chat_enabled = db.Column(db.Boolean, default=True)
Course.staff_chat_enabled  = db.Column(db.Boolean, default=True)
Course.completion_limit_days = db.Column(db.Integer, nullable=True)  # 4.3 срок прохождения после зачисления

# Урок теперь может лежать в главе ИЛИ подглаве
Lesson.section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=True)
Lesson.section = db.relationship("Section", backref=db.backref("lessons", cascade="all, delete-orphan"))

# Тест/Задание: политики оценивания и попытки
Test.grading_policy_json = db.Column(db.Text, nullable=True)        # JSON: {"per_attempt_scale": {"1":1,"2":0.8}, "manual_after_attempt": 3}
Assignment.grading_policy_json = db.Column(db.Text, nullable=True)  # Аналогично

# Новые типы вопросов (MATCH)
class MatchPair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    left_text = db.Column(db.String(256), nullable=False)
    right_text = db.Column(db.String(256), nullable=False)
    Question.matchpair_set = db.relationship("MatchPair", backref="question", cascade="all, delete-orphan")



# Приглашения в курс с ролью (по ссылке)
class CourseInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    role = db.Column(db.String(32), nullable=False)  # CourseRole.STUDENT|TEACHER|EDITOR
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    max_uses = db.Column(db.Integer, nullable=True)  # None = без ограничений
    used = db.Column(db.Integer, default=0)

    course = db.relationship("Course", backref=db.backref("invites", cascade="all, delete-orphan"))

    __table_args__ = (UniqueConstraint('course_id', 'token', name='uq_course_token'),)

# Ограничение попыток на уровне конкретного задания/теста уже есть,
# добавим ещё «окно доступа» к курсу на уровне Enrollment (старт и дедлайн)
class EnrollmentWindow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollment.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline_at = db.Column(db.DateTime, nullable=True)  # если completion_limit_days: started_at + days

    enrollment = db.relationship("Enrollment", backref=db.backref("window", uselist=False, cascade="all, delete-orphan"))