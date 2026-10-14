from sqlalchemy import func, or_, select

from app.extensions import db
from app.models import PasswordReplacement, User


class UserRepository:
    def find_by_email(self, email):
        return db.session.scalar(
            select(User).where(
                func.lower(func.trim(User.email)) == email.strip().lower()
            )
        )

    def find_by_exact_email(self, email):
        return db.session.scalar(select(User).where(User.email == email))

    def find_by_login_identifier(self, identifier):
        normalized = identifier.strip().lower()
        return db.session.scalar(
            select(User).where(
                or_(
                    func.lower(func.trim(User.email)) == normalized,
                    User.carnet == identifier.strip(),
                )
            )
        )

    def find_by_carnet(self, carnet):
        return db.session.scalar(select(User).where(User.carnet == carnet))

    def find_by_id(self, user_id):
        return db.session.get(User, user_id)

    def list_all(self):
        return db.session.scalars(select(User).order_by(User.name)).all()

    def list_by_role(self, role):
        return db.session.scalars(
            select(User).where(User.role == role).order_by(User.name)
        ).all()

    def list_by_ids(self, user_ids):
        if not user_ids:
            return []
        return db.session.scalars(
            select(User).where(User.id.in_(user_ids)).order_by(User.id)
        ).all()

    def list_students_with_carnet(self):
        return db.session.scalars(
            select(User).where(
                User.role == "alumno", User.carnet.is_not(None)
            )
        ).all()

    def stage(self, user):
        db.session.add(user)
        db.session.flush()
        return user

    def add(self, user):
        db.session.add(user)
        db.session.commit()
        return user

    def add_many(self, users):
        db.session.add_all(users)
        db.session.commit()
        return users

    def save(self, user):
        db.session.add(user)
        db.session.commit()
        return user

    def find_password_replacement(self, user_id):
        return db.session.get(PasswordReplacement, user_id)

    def delete_password_replacement(self, replacement):
        db.session.delete(replacement)

    def save_password_replacement(self, replacement):
        db.session.add(replacement)
        db.session.commit()
        return replacement

    def stage_password_replacement(self, replacement):
        db.session.add(replacement)
        return replacement

    def flush(self):
        db.session.flush()

    def commit_changes(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
