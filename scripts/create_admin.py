"""创建初始管理员账号。

用法（在 backend/ 目录下，通过 uv 执行）：
    uv run python ../scripts/create_admin.py --username admin --password <pwd>
不传 --password 时会自动生成随机密码并打印出来。
"""
import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Create initial admin user")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default=None, help="omit to auto-generate")
    ap.add_argument("--display-name", default="管理员")
    args = ap.parse_args()

    password = args.password or secrets.token_urlsafe(12)

    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.username == args.username))
        if existing is not None:
            print(f"用户 {args.username} 已存在，跳过创建")
            return
        user = User(
            username=args.username,
            password_hash=hash_password(password),
            display_name=args.display_name,
            role=UserRole.admin,
        )
        db.add(user)
        db.commit()
        print(f"管理员已创建: {args.username} / {password}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
