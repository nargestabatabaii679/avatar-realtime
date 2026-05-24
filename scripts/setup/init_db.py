"""
Initialize the database with default data.
Usage: python scripts/setup/init_db.py --admin-email admin@example.com --admin-password SecurePass123!
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parents[2] / "backend"))


async def main(admin_email: str, admin_password: str, org_name: str) -> None:
    from app.core.database import AsyncSessionLocal, init_db
    from app.core.security import get_password_hash
    from app.models.organization import Organization
    from app.models.user import User, UserRole
    from sqlalchemy import select

    print("Initializing database...")
    await init_db()
    print("✓ Tables created")

    async with AsyncSessionLocal() as db:
        # Check if org already exists
        existing_org = await db.scalar(select(Organization).limit(1))

        if not existing_org:
            org = Organization(
                id=uuid.uuid4(),
                name=org_name,
                slug=org_name.lower().replace(" ", "-"),
                plan="enterprise",
                max_users=1000,
                max_storage_gb=1000,
                max_videos_per_month=10000,
                is_active=True,
            )
            db.add(org)
            await db.flush()
            org_id = org.id
            print(f"✓ Organization created: {org_name}")
        else:
            org_id = existing_org.id
            print(f"✓ Using existing organization: {existing_org.name}")

        # Check if admin already exists
        existing_admin = await db.scalar(
            select(User).where(User.email == admin_email)
        )
        if existing_admin:
            print(f"ℹ Admin user already exists: {admin_email}")
        else:
            admin = User(
                id=uuid.uuid4(),
                email=admin_email,
                username=admin_email.split("@")[0],
                full_name="System Administrator",
                hashed_password=get_password_hash(admin_password),
                role=UserRole.SUPER_ADMIN,
                organization_id=org_id,
                is_active=True,
                is_verified=True,
                is_superuser=True,
            )
            db.add(admin)
            print(f"✓ Admin user created: {admin_email}")

        await db.commit()

    print("\n✓ Database initialization complete!")
    print(f"\nLogin credentials:\n  Email: {admin_email}\n  Password: {admin_password}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Avatar Platform database")
    parser.add_argument("--admin-email", required=True, help="Admin user email")
    parser.add_argument("--admin-password", required=True, help="Admin user password")
    parser.add_argument("--org-name", default="Default Organization", help="Organization name")
    args = parser.parse_args()

    asyncio.run(main(args.admin_email, args.admin_password, args.org_name))
