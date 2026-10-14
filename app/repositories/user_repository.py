from sqlalchemy import func, or_, select

from app.extensions import db
from app.models import User


class UserRepository:
    def find_by_email(self, email):
        return db.session.scalar(
            select(User).where(
                func.lower(func.trim(User.email)) == email.strip().lower()
            )
        )

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
