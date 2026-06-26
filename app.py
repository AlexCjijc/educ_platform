from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import math
import os, uuid
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, Course, CourseRoleMap, CourseRole, CourseVisibility, \
    Chapter, Lesson, Test, Question, AnswerOption, Assignment, Enrollment, LessonProgress, \
    TestAttempt, TestAnswer, AssignmentSubmission, Notification, Chat, ChatMessage, Review
from forms import RegisterForm, LoginForm
from permissions import can_edit_course, is_site_admin, is_site_moderator, is_course_staff
from grading import auto_grade_test
from datetime import datetime
import json
import secrets
from sqlalchemy import or_
from datetime import timedelta
from models import Section, MatchPair, CourseInvite, EnrollmentWindow
from urllib.parse import urlparse, parse_qs


from models import (
    db, User, Course, CourseRoleMap, CourseRole, CourseVisibility,
    Chapter, Section, Lesson, Test, Question, AnswerOption, MatchPair,
    Assignment, Enrollment, LessonProgress, TestAttempt, TestAnswer,
    AssignmentSubmission, Notification, Chat, ChatMessage, Review,
    CourseInvite, EnrollmentWindow
)
from permissions import can_edit_course, is_site_admin, is_course_staff, is_site_moderator
from grading import auto_grade_test


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = "login"

with app.app_context():
    up_rel = app.config.get('UPLOAD_COURSE_DIR', 'uploads/courses')
    os.makedirs(os.path.join(app.static_folder, app.config.get('UPLOAD_AVATAR_DIR', 'uploads/avatars')), exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, up_rel), exist_ok=True)


def _allowed_image(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png','jpg','jpeg','webp','gif'})

def _save_course_image(fs, course_id: int) -> str|None:
    """
    Сохранить FileStorage в static/uploads/courses и вернуть относительный путь,
    который можно пробросить в url_for('static', filename=rel_path).
    """
    if not fs or fs.filename == '' or not _allowed_image(fs.filename):
        return None
    ext = secure_filename(fs.filename).rsplit('.', 1)[-1].lower()
    fname = f"{course_id}_{uuid.uuid4().hex}.{ext}"
    rel_dir = app.config.get('UPLOAD_COURSE_DIR', 'uploads/courses')
    rel_path = f"{rel_dir}/{fname}"
    abs_path = os.path.join(app.static_folder, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    fs.save(abs_path)
    return rel_path


def _save_user_avatar(fs, user_id: int) -> str|None:
    """
    Сохранить FileStorage в static/uploads/avatars и вернуть относительный путь
    (для url_for('static', filename=rel_path)).
    """
    if not fs or fs.filename == '' or not _allowed_image(fs.filename):
        return None
    ext = secure_filename(fs.filename).rsplit('.', 1)[-1].lower()
    fname = f"user_{user_id}_{uuid.uuid4().hex}.{ext}"
    rel_dir = app.config.get('UPLOAD_AVATAR_DIR', 'uploads/avatars')
    rel_path = f"{rel_dir}/{fname}"
    abs_path = os.path.join(app.static_folder, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    fs.save(abs_path)
    return rel_path

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

@app.route("/")
def index():
    popular = Course.query.order_by(Course.rating.desc()).limit(6).all()
    newest = Course.query.order_by(Course.created_at.desc()).limit(6).all()
    authors = db.session.query(User).join(Course, Course.creator_id == User.id)\
        .group_by(User.id).order_by(User.rating.desc()).limit(8).all()
    return render_template("index.html", popular=popular, newest=newest, authors=authors)


@app.route("/catalog")
def catalog():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 9

    if page < 1:
        page = 1

    query = Course.query
    if q:
        like = f"%{q}%"
        # Если у Course нет поля category — удалите строку с Course.category.ilike(like)
        query = query.filter(or_(
            Course.title.ilike(like),
            Course.description.ilike(like),
            Course.category.ilike(like)
        ))

    total = query.count()
    pages = max(1, math.ceil(total / per_page))
    if page > pages:
        page = pages

    courses = (query
               .order_by(Course.created_at.desc())
               .offset((page - 1) * per_page)
               .limit(per_page)
               .all())

    return render_template(
        "catalog.html",
        courses=courses,
        q=q,
        page=page,
        pages=pages,
        total=total
    )




# Регистрация / логин
@app.route("/register", methods=["GET","POST"])
def register():
    form = RegisterForm(request.form)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        bio = (request.form.get("bio") or "").strip()
        avatar_fs = request.files.get("avatar")

        # простейшая валидация
        if not name or not email or not password:
            flash("Заполните имя, email и пароль", "error")
            return render_template("auth_register.html", form=form)

        if User.query.filter_by(email=email).first():
            flash("Email уже занят", "error")
            return render_template("auth_register.html", form=form)

        u = User(
            email=email, name=name,
            password_hash=generate_password_hash(password),
            bio=bio or None
        )
        db.session.add(u); db.session.commit()

        # сохранить аватар
        if avatar_fs and avatar_fs.filename:
            rel = _save_user_avatar(avatar_fs, u.id)
            if rel:
                u.avatar_path = rel
                db.session.commit()

        login_user(u)
        return redirect(url_for("index"))
    return render_template("auth_register.html", form=form)

@app.route("/login", methods=["GET","POST"])
def login():
    form = LoginForm(request.form)
    if request.method == "POST" and form.validate():
        u = User.query.filter_by(email=form.email.data).first()
        if not u or not check_password_hash(u.password_hash, form.password.data):
            flash("Неверные учетные данные", "error")
            return render_template("auth_login.html", form=form)
        login_user(u)
        return redirect(url_for("index"))
    return render_template("auth_login.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# Страница инвайта (просмотр + кнопка принять)
@app.route("/invite/<token>", methods=["GET"])
def invite_page(token):
    inv = CourseInvite.query.filter_by(token=token).first_or_404()
    # Проверки срока/лимитов
    expired = bool(inv.expires_at and inv.expires_at < datetime.utcnow())
    limit_reached = bool(inv.max_uses and inv.used >= inv.max_uses)
    return render_template("invite_page.html", invite=inv, expired=expired, limit_reached=limit_reached)

# Принять инвайт
@app.route("/invite/<token>/accept", methods=["POST"])
@login_required
def invite_accept(token):
    inv = CourseInvite.query.filter_by(token=token).first_or_404()
    # Проверка срока/лимита
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        flash("Ссылка просрочена", "error")
        return redirect(url_for("invite_page", token=token))
    if inv.max_uses and inv.used >= inv.max_uses:
        flash("Лимит использований исчерпан", "error")
        return redirect(url_for("invite_page", token=token))

    # Назначаем роль
    crm = CourseRoleMap.query.filter_by(course_id=inv.course_id, user_id=current_user.id).first()
    if crm:
        crm.role = inv.role
    else:
        db.session.add(CourseRoleMap(course_id=inv.course_id, user_id=current_user.id, role=inv.role))

    # Для STUDENT зачислим в курс (если ещё нет)
    if inv.role == CourseRole.STUDENT:
        if not Enrollment.query.filter_by(course_id=inv.course_id, user_id=current_user.id).first():
            db.session.add(Enrollment(course_id=inv.course_id, user_id=current_user.id))

    inv.used += 1
    db.session.commit()

    flash("Приглашение принято", "success")
    return redirect(url_for("course_learn", course_id=inv.course_id))


# Создание курса
@app.route("/course/new", methods=["GET","POST"])
@login_required
def course_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        desc = request.form.get("description", "").strip()
        visibility = request.form.get("visibility", CourseVisibility.PUBLIC)
        require_seq = request.form.get("require_sequence") == "on"
        max_students = request.form.get("max_students") or None
        category = (request.form.get("category") or "").strip() or None
        image_fs = request.files.get("image")

        c = Course(
            title=title, description=desc, creator_id=current_user.id,
            visibility=visibility, require_sequence=require_seq,
            max_students=int(max_students) if max_students else None,
            category=category
        )
        db.session.add(c); db.session.commit()

        # обложка
        if image_fs and image_fs.filename:
            rel_path = _save_course_image(image_fs, c.id)
            if rel_path:
                c.image_path = rel_path
                db.session.commit()

        db.session.add(CourseRoleMap(course_id=c.id, user_id=current_user.id, role=CourseRole.CREATOR))
        db.session.add(Chat(course_id=c.id))
        db.session.commit()
        return redirect(url_for("course_edit", course_id=c.id))
    return render_template("course_new.html")

# Редактирование курса (админка курса)
@app.route("/course/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
def course_edit(course_id):
    c = Course.query.get_or_404(course_id)
    if not can_edit_course(current_user.id, course_id) and not is_site_admin():
        abort(403)

    if request.method == "POST" and not request.is_json:
        action = request.form.get("action")

        if action == "add_chapter":
            title = request.form.get("chapter_title","").strip()
            if title:
                ch = Chapter(course_id=course_id, title=title, order_idx=len(c.chapters))
                db.session.add(ch); db.session.commit()
            return redirect(url_for("course_edit", course_id=course_id))

        elif action == "add_section":
            ch_id = int(request.form["chapter_id"])
            title = request.form.get("section_title","").strip()
            if title:
                s = Section(chapter_id=ch_id, title=title, order_idx=0)
                db.session.add(s); db.session.commit()
            return redirect(url_for("course_edit", course_id=course_id))

        elif action == "add_lesson":
            parent_type = request.form.get("parent_type", "chapter")
            title = (request.form.get("lesson_title") or "").strip()
            html = request.form.get("lesson_html") or ""
            video_url = (request.form.get("video_url") or "").strip() or None
            files = (request.form.get("external_files") or "").strip() or None

            if title:
                if parent_type == "section":
                    section_id = int(request.form["section_id"])
                    sec = Section.query.get_or_404(section_id)
                    lesson = Lesson(
                        chapter_id=sec.chapter_id,            # ВАЖНО: NOT NULL
                        section_id=section_id,
                        title=title, html_content=html,
                        video_url=video_url, external_files=files,
                        order_idx=Lesson.query.filter_by(section_id=section_id).count()
                    )
                else:
                    chapter_id = int(request.form["chapter_id"])
                    lesson = Lesson(
                        chapter_id=chapter_id, section_id=None,
                        title=title, html_content=html,
                        video_url=video_url, external_files=files,
                        order_idx=Lesson.query.filter_by(chapter_id=chapter_id, section_id=None).count()
                    )
                db.session.add(lesson); db.session.commit()
            return redirect(url_for("course_edit", course_id=course_id))

        elif action == "add_test":
            parent_type = request.form.get("parent_type", "chapter")
            title = (request.form.get("test_title") or "").strip()
            time_limit = int(request.form["time_limit_sec"]) if request.form.get("time_limit_sec") else None
            max_attempts = int(request.form["max_attempts"]) if request.form.get("max_attempts") else None
            auto_grade = ("auto_grade" in request.form)

            if title:
                if parent_type == "section":
                    section_id = int(request.form["section_id"])
                    sec = Section.query.get_or_404(section_id)
                    t = Test(
                        chapter_id=sec.chapter_id, section_id=section_id,
                        title=title, time_limit_sec=time_limit, max_attempts=max_attempts,
                        auto_grade=auto_grade,
                        order_idx=Test.query.filter_by(section_id=section_id).count()
                    )
                else:
                    chapter_id = int(request.form["chapter_id"])
                    t = Test(
                        chapter_id=chapter_id, section_id=None,
                        title=title, time_limit_sec=time_limit, max_attempts=max_attempts,
                        auto_grade=auto_grade,
                        order_idx=Test.query.filter_by(chapter_id=chapter_id, section_id=None).count()
                    )
                db.session.add(t); db.session.commit()
            return redirect(url_for("course_edit", course_id=course_id))

        elif action == "add_assignment":
            parent_type = request.form.get("parent_type", "chapter")
            title = (request.form.get("as_title") or "").strip()
            desc = request.form.get("as_desc") or ""
            time_limit = int(request.form["as_time"]) if request.form.get("as_time") else None
            max_attempts = int(request.form["as_attempts"]) if request.form.get("as_attempts") else None
            auto_grade = ("as_auto" in request.form)

            if title:
                if parent_type == "section":
                    section_id = int(request.form["section_id"])
                    sec = Section.query.get_or_404(section_id)
                    a = Assignment(
                        chapter_id=sec.chapter_id, section_id=section_id,
                        title=title, description=desc,
                        time_limit_sec=time_limit, max_attempts=max_attempts, auto_grade=auto_grade,
                        order_idx=Assignment.query.filter_by(section_id=section_id).count()
                    )
                else:
                    chapter_id = int(request.form["chapter_id"])
                    a = Assignment(
                        chapter_id=chapter_id, section_id=None,
                        title=title, description=desc,
                        time_limit_sec=time_limit, max_attempts=max_attempts, auto_grade=auto_grade,
                        order_idx=Assignment.query.filter_by(chapter_id=chapter_id, section_id=None).count()
                    )
                db.session.add(a); db.session.commit()
            return redirect(url_for("course_edit", course_id=course_id))

        if action == "assign_role":
            uid = int(request.form["user_id"])
            role = request.form.get("role", CourseRole.STUDENT)
            # upsert
            crm = CourseRoleMap.query.filter_by(course_id=course_id, user_id=uid).first()
            if crm:
                crm.role = role
            else:
                db.session.add(CourseRoleMap(course_id=course_id, user_id=uid, role=role))
            db.session.commit()
            flash("Роль назначена", "success")
            return redirect(url_for("course_edit", course_id=course_id))

            # Удалить участника из команды (только маппинг роли)
        if action == "remove_member":
            uid = int(request.form["user_id"])
            CourseRoleMap.query.filter_by(course_id=course_id, user_id=uid).delete()
            db.session.commit()
            flash("Участник удалён из команды", "success")
            return redirect(url_for("course_edit", course_id=course_id))

            # Создать инвайт
        if action == "create_invite":
            role = request.form.get("role", CourseRole.STUDENT)
            ttl_days = int(request.form["ttl_days"]) if request.form.get("ttl_days") else None
            max_uses = int(request.form["max_uses"]) if request.form.get("max_uses") else None
            token = secrets.token_urlsafe(16)
            inv = CourseInvite(
                course_id=course_id,
                role=role,
                token=token,
                expires_at=(datetime.utcnow() + timedelta(days=ttl_days)) if ttl_days else None,
                max_uses=max_uses
            )
            db.session.add(inv);
            db.session.commit()
            flash("Инвайт создан", "success")
            return redirect(url_for("course_edit", course_id=course_id))

            # Отозвать инвайт
        if action == "revoke_invite":
            invite_id = int(request.form["invite_id"])
            CourseInvite.query.filter_by(id=invite_id, course_id=course_id).delete()
            db.session.commit()
            flash("Инвайт отозван", "success")
            return redirect(url_for("course_edit", course_id=course_id))

    # GET
    c = Course.query.get_or_404(course_id)
    staff = (db.session.query(CourseRoleMap)
             .filter_by(course_id=course_id)
             .join(User)  # чтобы был m.user
             .all())
    invites = CourseInvite.query.filter_by(course_id=course_id) \
        .order_by(CourseInvite.created_at.desc()).all()

    return render_template("course_edit.html",
                           course=c,
                           staff=staff,
                           invites=invites)


def _chapter_course_id(ch: Chapter) -> int:
    return ch.course_id

def _section_course_id(sec: Section) -> int:
    return sec.chapter.course_id


def _lesson_course_id(lesson):
    # Урок может быть у главы или у подглавы
    if getattr(lesson, "chapter_id", None):
        return lesson.chapter.course_id
    if getattr(lesson, "section_id", None) and lesson.section is not None:
        return lesson.section.chapter.course_id
    # fallback
    return lesson.chapter.course_id

def _embed_url(video_url: str|None) -> str|None:
    if not video_url:
        return None
    try:
        u = urlparse(video_url)
        host = (u.netloc or "").lower()
        if "youtube.com" in host:
            # https://www.youtube.com/watch?v=ID
            q = parse_qs(u.query)
            vid = q.get("v", [None])[0]
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
            # https://www.youtube.com/embed/ID (уже embed)
            if "/embed/" in u.path:
                return video_url
        if "youtu.be" in host:
            # https://youtu.be/ID
            vid = u.path.strip("/").split("/")[0]
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
        if "rutube.ru" in host:
            # https://rutube.ru/video/<ID>/
            parts = [p for p in u.path.strip("/").split("/") if p]
            if len(parts) >= 2 and parts[0] == "video":
                vid = parts[1]
                return f"https://rutube.ru/play/embed/{vid}"
            # уже embed
            if "/play/embed/" in u.path:
                return video_url
    except Exception:
        return None
    return None

@app.route("/lesson/<int:lesson_id>")
@login_required
def lesson_view(lesson_id):
    l = Lesson.query.get_or_404(lesson_id)
    course_id = _lesson_course_id(l)
    # Доступ: участник курса или персонал курса (или сайт-админ)
    enr = Enrollment.query.filter_by(course_id=course_id, user_id=current_user.id).first()
    if not enr and not is_course_staff(current_user.id, course_id) and not is_site_admin():
        flash("Просмотр урока доступен только участникам курса", "error")
        return redirect(url_for("course_detail", course_id=course_id))

    embed = _embed_url(l.video_url)
    return render_template("lesson_view.html", lesson=l, course_id=course_id, video_embed=embed)

def _ensure_can_edit(course_id:int):
    if not (current_user.is_authenticated and (can_edit_course(current_user.id, course_id) or is_site_admin())):
        abort(403)

@app.route("/course/<int:course_id>/reorder", methods=["POST"])
@login_required
def course_reorder(course_id):
    _ensure_can_edit(course_id)
    # валидируем курс
    Course.query.get_or_404(course_id)

    data = request.get_json(silent=True) or {}
    chapters_payload = data.get("chapters") or []

    try:
        # мапы курса
        chapters = {c.id: c for c in Chapter.query.filter_by(course_id=course_id).all()}
        sections = {}
        for ch in chapters.values():
            for sec in ch.sections:
                sections[sec.id] = sec

        # ленивые кеши юнитов
        lesson_cache, test_cache, assign_cache = {}, {}, {}

        def get_lesson(i):
            if i not in lesson_cache:
                lesson_cache[i] = Lesson.query.get(i)
            return lesson_cache[i]

        def get_test(i):
            if i not in test_cache:
                test_cache[i] = Test.query.get(i)
            return test_cache[i]

        def get_assign(i):
            if i not in assign_cache:
                assign_cache[i] = Assignment.query.get(i)
            return assign_cache[i]

        def place_unit(u, ch_id, sec_id, idx):
            t = u.get('t')
            uid = int(u.get('id'))
            if t == 'lesson':
                obj = get_lesson(uid)
            elif t == 'test':
                obj = get_test(uid)
            elif t == 'assignment':
                obj = get_assign(uid)
            else:
                obj = None
            if not obj:
                return
            # гарантируем принадлежность к курсу через главу
            if ch_id not in chapters:
                return
            if sec_id is None:
                obj.chapter_id = ch_id
                obj.section_id = None
            else:
                sec = sections.get(sec_id)
                if not sec:
                    # подглава могла быть перемещена чуть выше — достанем заново и примем
                    sec = Section.query.get(sec_id)
                    if not sec or sec.chapter_id not in chapters:
                        return
                    sections[sec_id] = sec
                obj.section_id = sec_id
                obj.chapter_id = sec.chapter_id
            obj.order_idx = idx

        for ch_idx, chd in enumerate(chapters_payload):
            ch_id = int(chd.get('id'))
            ch = chapters.get(ch_id)
            if not ch:
                continue
            ch.order_idx = ch_idx

            # юниты в самой главе
            for idx, u in enumerate(chd.get('items', [])):
                place_unit(u, ch_id, None, idx)

            # подглавы
            for s_idx, sd in enumerate(chd.get('sections', [])):
                sec_id = int(sd.get('id'))
                sec = sections.get(sec_id)
                if not sec:
                    sec = Section.query.get(sec_id)
                    if not sec or sec.chapter_id not in chapters:
                        continue
                    sections[sec_id] = sec
                # если подглаву перенесли
                if sec.chapter_id != ch_id:
                    sec.chapter_id = ch_id
                # порядок подглав (если используете)
                if hasattr(sec, 'order_idx'):
                    sec.order_idx = s_idx

                # юниты подглавы
                for idx, u in enumerate(sd.get('items', [])):
                    place_unit(u, ch_id, sec_id, idx)

        db.session.commit()
        return jsonify(ok=True)
    except Exception as e:
        db.session.rollback()
        import traceback; traceback.print_exc()
        return jsonify(ok=False, error=str(e)), 500

# Удаление сущностей
@app.route("/chapter/<int:chapter_id>/delete", methods=["POST"])
@login_required
def chapter_delete(chapter_id):
    ch = Chapter.query.get_or_404(chapter_id)
    _ensure_can_edit(ch.course_id)
    db.session.delete(ch); db.session.commit()
    return jsonify(ok=True)

@app.route("/section/<int:section_id>/delete", methods=["POST"])
@login_required
def section_delete(section_id):
    s = Section.query.get_or_404(section_id)
    _ensure_can_edit(s.chapter.course_id)
    db.session.delete(s); db.session.commit()
    return jsonify(ok=True)

@app.route("/lesson/<int:lesson_id>/delete", methods=["POST"])
@login_required
def lesson_delete(lesson_id):
    l = Lesson.query.get_or_404(lesson_id)
    course_id = l.chapter.course_id if l.chapter_id else (l.section.chapter.course_id if l.section_id else None)
    if course_id is None: abort(400)
    _ensure_can_edit(course_id)
    db.session.delete(l); db.session.commit()
    return jsonify(ok=True)

@app.route("/test/<int:test_id>/delete", methods=["POST"])
@login_required
def test_delete(test_id):
    t = Test.query.get_or_404(test_id)
    _ensure_can_edit(t.chapter.course_id)
    db.session.delete(t); db.session.commit()
    return jsonify(ok=True)

@app.route("/assignment/<int:assignment_id>/delete", methods=["POST"])
@login_required
def assignment_delete(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    _ensure_can_edit(a.chapter.course_id)
    db.session.delete(a); db.session.commit()
    return jsonify(ok=True)


@app.route("/lesson/<int:lesson_id>/editor", methods=["GET", "POST"])
@login_required
def lesson_editor(lesson_id):
    l = Lesson.query.get_or_404(lesson_id)
    course_id = _lesson_course_id(l)
    if not can_edit_course(current_user.id, course_id) and not is_site_admin():
        abort(403)

    if request.method == "POST":
        l.title = (request.form.get("title") or l.title).strip()
        l.video_url = (request.form.get("video_url") or "").strip() or None
        l.external_files = (request.form.get("external_files") or "").strip() or None
        l.html_content = request.form.get("html_content") or ""

        # ВАЖНО: состояние панели компилятора
        l.code_panel_enabled = bool(request.form.get("code_panel_enabled"))
        lang = (request.form.get("code_language") or "").strip() or None
        l.code_language = lang if l.code_panel_enabled else None

        db.session.commit()
        if request.form.get("close") == "1":
            return redirect(url_for("course_edit", course_id=course_id))
        return redirect(url_for("lesson_editor", lesson_id=lesson_id))

    return render_template("lesson_editor.html", lesson=l, course_id=course_id)

# Страница курса (описание + отзывы)
@app.route("/course/<int:course_id>")
def course_detail(course_id):
    c = Course.query.get_or_404(course_id)
    reviews = Review.query.filter_by(course_id=course_id).order_by(Review.created_at.desc()).all()
    return render_template("course_detail.html", course=c, reviews=reviews)

# Подписка/отписка (начать курс / отказаться)
@app.route("/course/<int:course_id>/enroll", methods=["POST"])
@login_required
def course_enroll(course_id):
    c = Course.query.get_or_404(course_id)
    if c.visibility == CourseVisibility.PRIVATE and not is_course_staff(current_user.id, c.id):
        token = request.form.get("invite_token","")
        if not token or token != (c.invite_token or ""):
            flash("Неверный токен приглашения", "error")
            return redirect(url_for("course_detail", course_id=course_id))
    if c.max_students:
        count = Enrollment.query.filter_by(course_id=course_id).count()
        if count >= c.max_students:
            flash("Достигнут лимит участников", "error")
            return redirect(url_for("course_detail", course_id=course_id))

    exists = Enrollment.query.filter_by(course_id=course_id, user_id=current_user.id).first()
    if not exists:
        db.session.add(Enrollment(course_id=course_id, user_id=current_user.id))
        db.session.add(CourseRoleMap(course_id=course_id, user_id=current_user.id, role=CourseRole.STUDENT))
        db.session.commit()
        # создать окно прохождения от момента зачисления
    if c.completion_limit_days:
        en = Enrollment.query.filter_by(course_id=course_id, user_id=current_user.id).first()
        if en and not EnrollmentWindow.query.filter_by(enrollment_id=en.id).first():
            db.session.add(EnrollmentWindow(
                enrollment_id=en.id,
                started_at=datetime.utcnow(),
                deadline_at=datetime.utcnow() + timedelta(days=c.completion_limit_days)
            ))
            db.session.commit()
    return redirect(url_for("course_learn", course_id=course_id))

@app.route("/course/<int:course_id>/leave", methods=["POST"])
@login_required
def course_leave(course_id):
    Enrollment.query.filter_by(course_id=course_id, user_id=current_user.id).delete()
    CourseRoleMap.query.filter_by(course_id=course_id, user_id=current_user.id, role=CourseRole.STUDENT).delete()
    db.session.commit()
    return redirect(url_for("my_learning"))

# Прохождение курса
@app.route("/course/<int:course_id>/learn")
@login_required
def course_learn(course_id):
    c = Course.query.get_or_404(course_id)
    enr = Enrollment.query.filter_by(course_id=course_id, user_id=current_user.id).first()
    if not enr and not is_course_staff(current_user.id, c.id):
        return redirect(url_for("course_detail", course_id=course_id))
    return render_template("course_learn.html", course=c)

# Отметить урок завершённым
@app.route("/lesson/<int:lesson_id>/complete", methods=["POST"])
@login_required
def lesson_complete(lesson_id):
    lp = LessonProgress.query.filter_by(lesson_id=lesson_id, user_id=current_user.id).first()
    if not lp:
        lp = LessonProgress(lesson_id=lesson_id, user_id=current_user.id, completed=True, completed_at=datetime.utcnow())
        db.session.add(lp)
    else:
        lp.completed = True
        lp.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})

# Страница теста
@app.route("/test/<int:test_id>")
@login_required
def test_view(test_id):
    t = Test.query.get_or_404(test_id)
    return render_template("course_test.html", test=t)

# Отправка ответов по тесту
@app.route("/test/<int:test_id>/submit", methods=["POST"])
@login_required
def test_submit(test_id):
    t = Test.query.get_or_404(test_id)


    # проверка лимитов попыток
    attempts = TestAttempt.query.filter_by(test_id=test_id, user_id=current_user.id).count()
    attempt_index = attempts + 1
    if t.max_attempts and attempts >= t.max_attempts:
        flash("Лимит попыток исчерпан", "error")
        return redirect(url_for("test_view", test_id=test_id))

    attempt = TestAttempt(test_id=test_id, user_id=current_user.id)
    db.session.add(attempt); db.session.commit()

    answers_by_qid = {}
    for q in t.questions:
        field = f"q_{q.id}"
        if q.qtype == "SINGLE":
            ans = request.form.get(field)
            answers_by_qid[q.id] = ans
            db.session.add(
                TestAnswer(attempt_id=attempt.id, question_id=q.id, selected_option_ids=str(ans) if ans else None))

        elif q.qtype in ("MULTI",):
            ans_list = request.form.getlist(field)
            answers_by_qid[q.id] = ans_list
            db.session.add(TestAnswer(attempt_id=attempt.id, question_id=q.id, selected_option_ids=",".join(ans_list)))

        elif q.qtype == "ORDER":
            raw = request.form.get(field, "")
            seq = [s.strip() for s in raw.split(",") if s.strip()]
            answers_by_qid[q.id] = seq
            db.session.add(TestAnswer(attempt_id=attempt.id, question_id=q.id, selected_option_ids=",".join(seq)))

        elif q.qtype == "MATCH":
            raw = request.form.get(field, "")
            pairs = [s.strip() for s in raw.split(",") if ":" in s]
            answers_by_qid[q.id] = pairs
            db.session.add(TestAnswer(attempt_id=attempt.id, question_id=q.id, selected_option_ids=",".join(pairs)))

        elif q.qtype == "TEXT":
            txt = request.form.get(field, "")
            answers_by_qid[q.id] = None
            db.session.add(TestAnswer(attempt_id=attempt.id, question_id=q.id, text_answer=txt))

        else:
            ans = request.form.get(field)
            answers_by_qid[q.id] = ans
            db.session.add(
                TestAnswer(attempt_id=attempt.id, question_id=q.id, selected_option_ids=str(ans) if ans else None))

    if t.auto_grade:
        from grading import auto_grade_test
        score, max_score, manual_required = auto_grade_test(t, t.questions, answers_by_qid, attempt_index)
        attempt.score = score
        attempt.max_score = max_score
        attempt.graded = not manual_required
        attempt.manual_required = manual_required
        attempt.finished_at = datetime.utcnow()
        db.session.commit()

        # уведомление студенту
        n = Notification(user_id=current_user.id, ntype="GRADE_PUBLISHED",
                         payload=json.dumps({"test_id": t.id, "score": score, "max": max_score}))
        db.session.add(n); db.session.commit()
    else:
        attempt.manual_required = True
        attempt.finished_at = datetime.utcnow()
        db.session.commit()
        # уведомление преподавателям
        staff_user_ids = [m.user_id for m in CourseRoleMap.query.filter_by(course_id=t.chapter.course_id).all()
                          if m.role in (CourseRole.CREATOR, CourseRole.TEACHER, CourseRole.EDITOR)]
        for uid in staff_user_ids:
            db.session.add(Notification(user_id=uid, ntype="NEED_GRADING",
                         payload=json.dumps({"test_id": t.id, "student_id": current_user.id, "attempt_id": attempt.id})))
        db.session.commit()

    flash("Ответы отправлены", "success")
    return redirect(url_for("test_view", test_id=test_id))

# Задание (текстовый ответ)
@app.route("/assignment/<int:assignment_id>/submit", methods=["POST"])
@login_required
def assignment_submit(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    attempts = AssignmentSubmission.query.filter_by(assignment_id=assignment_id, user_id=current_user.id).count()
    if a.max_attempts and attempts >= a.max_attempts:
        flash("Лимит попыток исчерпан", "error")
        return redirect(url_for("course_learn", course_id=a.chapter.course_id))

    text_answer = request.form.get("text_answer","")
    sub = AssignmentSubmission(assignment_id=assignment_id, user_id=current_user.id, text_answer=text_answer)
    db.session.add(sub); db.session.commit()

    if a.auto_grade:
        # простая автопроверка по ключевым словам (MVP)
        score = 1.0 if len(text_answer) >= 30 else 0.0
        sub.score = score
        sub.max_score = 1.0
        sub.graded = True
        db.session.commit()
        db.session.add(Notification(user_id=current_user.id, ntype="GRADE_PUBLISHED",
                                    payload=json.dumps({"assignment_id": a.id, "score": score, "max": 1.0})))
        db.session.commit()
    else:
        # уведомляем преподавателей
        staff_user_ids = [m.user_id for m in CourseRoleMap.query.filter_by(course_id=a.chapter.course_id).all()
                          if m.role in (CourseRole.CREATOR, CourseRole.TEACHER, CourseRole.EDITOR)]
        for uid in staff_user_ids:
            db.session.add(Notification(user_id=uid, ntype="NEED_GRADING",
                         payload=json.dumps({"assignment_id": a.id, "student_id": current_user.id, "submission_id": sub.id})))
        db.session.commit()

    flash("Ответ отправлен", "success")
    return redirect(url_for("course_learn", course_id=a.chapter.course_id))

# Чаты
@app.route("/course/<int:course_id>/chat", methods=["GET","POST"])
@login_required
def course_chat(course_id):
    chat = Chat.query.filter_by(course_id=course_id).first()
    if not chat:
        chat = Chat(course_id=course_id); db.session.add(chat); db.session.commit()

    if request.method == "POST":
        text = request.form.get("text","").strip()
        mentions = request.form.get("mentions","").strip()  # CSV user_ids
        if text:
            msg = ChatMessage(chat_id=chat.id, author_id=current_user.id, text=text, mentions=mentions or None)
            db.session.add(msg); db.session.commit()
            # Уведомления упомянутым
            if mentions:
                for uid in mentions.split(","):
                    if uid.isdigit():
                        db.session.add(Notification(user_id=int(uid), ntype="CHAT_MENTION",
                            payload=json.dumps({"course_id": course_id, "message_id": msg.id})))
                db.session.commit()

    msgs = ChatMessage.query.filter_by(chat_id=chat.id).order_by(ChatMessage.created_at.asc()).all()
    return render_template("chat_course.html", messages=msgs, course_id=course_id)

# Мои курсы
@app.route("/my")
@login_required
def my_learning():
    items = Enrollment.query.filter_by(user_id=current_user.id).all()
    return render_template("my_learning.html", items=items)

# Профиль
@app.route("/profile/<int:user_id>")
def profile(user_id):
    u = User.query.get_or_404(user_id)
    created = Course.query.filter_by(creator_id=u.id).all()
    passed = Enrollment.query.filter_by(user_id=u.id).all()
    return render_template("profile.html", u=u, created=created, passed=passed)

# Настройки (почта/пароль/уведомления — MVP только пароль)
@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")

        # Обновить профиль (имя, email, bio, аватар)
        if action == "update_profile":
            new_name = (request.form.get("name") or "").strip()
            new_email = (request.form.get("email") or "").strip().lower()
            new_bio = (request.form.get("bio") or "").strip()
            remove_avatar = request.form.get("remove_avatar") == "on"
            avatar_fs = request.files.get("avatar")

            if new_name:
                current_user.name = new_name
            if new_email and new_email != current_user.email:
                if User.query.filter(User.email == new_email, User.id != current_user.id).first():
                    flash("Этот email уже занят", "error")
                    return redirect(url_for("settings"))
                current_user.email = new_email
            current_user.bio = new_bio or None

            if remove_avatar:
                current_user.avatar_path = None
            if avatar_fs and avatar_fs.filename:
                rel = _save_user_avatar(avatar_fs, current_user.id)
                if rel:
                    current_user.avatar_path = rel

            db.session.commit()
            flash("Профиль обновлён", "success")
            return redirect(url_for("settings"))

        # Смена пароля
        if action == "update_password":
            current_pw = request.form.get("current_password") or ""
            new_pw = request.form.get("new_password") or ""
            if not check_password_hash(current_user.password_hash, current_pw):
                flash("Неверный текущий пароль", "error")
                return redirect(url_for("settings"))
            if len(new_pw) < 6:
                flash("Новый пароль слишком короткий", "error")
                return redirect(url_for("settings"))
            current_user.password_hash = generate_password_hash(new_pw)
            db.session.commit()
            flash("Пароль обновлён", "success")
            return redirect(url_for("settings"))

    return render_template("settings.html", u=current_user)


# Уведомления
@app.route("/notifications")
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template("notifications.html", items=items)

@app.route("/course/<int:course_id>/settings", methods=["GET","POST"])
@login_required
def course_settings(course_id):
    c = Course.query.get_or_404(course_id)
    if not can_edit_course(current_user.id, course_id) and not is_site_admin():
        abort(403)

    if request.method == "POST":
        c.title = (request.form.get("title") or c.title).strip()
        c.description = (request.form.get("description") or c.description).strip()
        c.visibility = request.form.get("visibility", c.visibility)
        c.require_sequence = bool(request.form.get("require_sequence"))
        c.max_students = int(request.form["max_students"]) if request.form.get("max_students") else None
        c.access_start = datetime.fromisoformat(request.form["access_start"]) if request.form.get("access_start") else None
        c.access_end   = datetime.fromisoformat(request.form["access_end"]) if request.form.get("access_end") else None
        c.completion_limit_days = int(request.form["completion_limit_days"]) if request.form.get("completion_limit_days") else None

        # Новое: категория/картинка
        c.category = (request.form.get("category") or "").strip() or None
        if request.form.get("remove_image") == "on":
            c.image_path = None
        image_fs = request.files.get("image")
        if image_fs and image_fs.filename:
            rel_path = _save_course_image(image_fs, c.id)
            if rel_path:
                c.image_path = rel_path

        # чаты/инвайт как у вас уже было...
        c.public_chat_enabled = bool(request.form.get("public_chat_enabled"))
        c.staff_chat_enabled  = bool(request.form.get("staff_chat_enabled"))
        if request.form.get("regen_invite") and c.visibility == CourseVisibility.PRIVATE:
            c.invite_token = secrets.token_urlsafe(16)

        db.session.commit()
        flash("Настройки курса сохранены", "success")
        return redirect(url_for("course_settings", course_id=course_id))

    return render_template("course_settings.html", course=c)


def _delete_course_safely(course_id: int):
    c = Course.query.get_or_404(course_id)

    # Удаляем зависимые объекты, где нет каскада:
    # роли в курсе
    CourseRoleMap.query.filter_by(course_id=course_id).delete(synchronize_session=False)
    # участия
    enr_ids = [e.id for e in Enrollment.query.filter_by(course_id=course_id).all()]
    if enr_ids:
        EnrollmentWindow.query.filter(EnrollmentWindow.enrollment_id.in_(enr_ids)).delete(synchronize_session=False)
    Enrollment.query.filter_by(course_id=course_id).delete(synchronize_session=False)
    # уведомления, связанные с курсом — мягкая очистка по payload (MVP: оставим)
    # инвайты
    CourseInvite.query.filter_by(course_id=course_id).delete(synchronize_session=False)
    # чаты и сообщения
    chat_ids = [ch.id for ch in Chat.query.filter_by(course_id=course_id).all()]
    if chat_ids:
        ChatMessage.query.filter(ChatMessage.chat_id.in_(chat_ids)).delete(synchronize_session=False)
        Chat.query.filter_by(course_id=course_id).delete(synchronize_session=False)
    # отзывы
    Review.query.filter_by(course_id=course_id).delete(synchronize_session=False)

    # Главы/подглавы/уроки/тесты/вопросы/варианты/задания удалятся каскадом
    # (Chapter.backref(cascade="all, delete-orphan"), Section/Lesson/Test/Assignment аналогично)

    db.session.delete(c)
    db.session.commit()

@app.route("/course/<int:course_id>/delete", methods=["POST"])
@login_required
def course_delete(course_id):
    c = Course.query.get_or_404(course_id)
    if not can_edit_course(current_user.id, course_id) and not is_site_admin():
        abort(403)
    _delete_course_safely(course_id)
    flash("Курс удалён", "success")
    return redirect(url_for("catalog"))


@app.route("/test/<int:test_id>/editor", methods=["GET", "POST"])
@login_required
def test_editor(test_id):
    t = Test.query.get_or_404(test_id)
    course_id = t.chapter.course_id
    if not can_edit_course(current_user.id, course_id) and not is_site_admin():
        abort(403)

    if request.method == "POST":
        t.title = request.form.get("title", t.title).strip()
        t.time_limit_sec = int(request.form["time_limit_sec"]) if request.form.get("time_limit_sec") else None
        t.max_attempts = int(request.form["max_attempts"]) if request.form.get("max_attempts") else None
        t.auto_grade = bool(request.form.get("auto_grade"))
        t.grading_policy_json = request.form.get("grading_policy_json") or None
        db.session.commit()
        flash("Тест сохранён", "success")
        if request.form.get("close") == "1":
            return redirect(url_for("course_edit", course_id=course_id))
    # Для удобства в редакторе покажем список вопросов
    return render_template("test_editor.html", test=t, course_id=course_id)


@app.route("/assignment/<int:assignment_id>/editor", methods=["GET", "POST"])
@login_required
def assignment_editor(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    course_id = a.chapter.course_id
    if not can_edit_course(current_user.id, course_id) and not is_site_admin():
        abort(403)

    if request.method == "POST":
        a.title = request.form.get("title", a.title).strip()
        a.description = request.form.get("description", a.description)
        a.time_limit_sec = int(request.form["time_limit_sec"]) if request.form.get("time_limit_sec") else None
        a.max_attempts = int(request.form["max_attempts"]) if request.form.get("max_attempts") else None
        a.auto_grade = bool(request.form.get("auto_grade"))
        a.grading_policy_json = request.form.get("grading_policy_json") or None
        db.session.commit()
        flash("Задание сохранено", "success")
        if request.form.get("close") == "1":
            return redirect(url_for("course_edit", course_id=course_id))
    return render_template("assignment_editor.html", assignment=a, course_id=course_id)


@app.route("/invite/<token>/accept", methods=["POST"])
@login_required
def accept_invite(token):
    inv = CourseInvite.query.filter_by(token=token).first_or_404()
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        flash("Ссылка просрочена", "error"); return redirect(url_for("course_detail", course_id=inv.course_id))
    if inv.max_uses and inv.used >= inv.max_uses:
        flash("Лимит использований исчерпан", "error"); return redirect(url_for("course_detail", course_id=inv.course_id))

    # выдать роль и записать в курс (если не записан — записать как студент)
    m = CourseRoleMap.query.filter_by(course_id=inv.course_id, user_id=current_user.id).first()
    if not m:
        db.session.add(CourseRoleMap(course_id=inv.course_id, user_id=current_user.id, role=inv.role))
    else:
        m.role = inv.role

    # для ролей STAFF не обязательно, но чаще всего нужно зачисление:
    if inv.role == CourseRole.STUDENT:
        if not Enrollment.query.filter_by(course_id=inv.course_id, user_id=current_user.id).first():
            db.session.add(Enrollment(course_id=inv.course_id, user_id=current_user.id))

    inv.used += 1
    db.session.commit()
    flash("Приглашение принято", "success")
    return redirect(url_for("course_edit", course_id=inv.course_id))


# Админка сайта (MVP: список пользователей/курсов)
@app.route("/admin")
@login_required
def admin_dashboard():
    if not is_site_moderator():
        abort(403)
    users = User.query.order_by(User.created_at.desc()).limit(50).all()
    courses = Course.query.order_by(Course.created_at.desc()).limit(50).all()
    return render_template("admin_dashboard.html", users=users, courses=courses)

if __name__ == "__main__":
    app.run(debug=True)

