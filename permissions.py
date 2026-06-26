from flask_login import current_user
from models import SiteRole, CourseRoleMap, CourseRole

def is_site_admin():
    return current_user.is_authenticated and current_user.site_role in {SiteRole.OWNER, SiteRole.ADMIN}

def is_site_moderator():
    return current_user.is_authenticated and current_user.site_role in {SiteRole.OWNER, SiteRole.ADMIN, SiteRole.MODERATOR}

def course_role(user_id, course_id):
    crm = CourseRoleMap.query.filter_by(user_id=user_id, course_id=course_id).first()
    return crm.role if crm else None

def can_edit_course(user_id, course_id):
    return course_role(user_id, course_id) in {CourseRole.CREATOR, CourseRole.TEACHER, CourseRole.EDITOR}

def is_course_staff(user_id, course_id):
    return course_role(user_id, course_id) in {CourseRole.CREATOR, CourseRole.TEACHER, CourseRole.EDITOR}
