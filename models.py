from dataclasses import dataclass
from flask_login import UserMixin


@dataclass
class User(UserMixin):
    id: int
    username: str
    password_hash: str
    role: str = "analyst"

    @staticmethod
    def from_row(row):
        if row is None:
            return None
        return User(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=row["role"],
        )
