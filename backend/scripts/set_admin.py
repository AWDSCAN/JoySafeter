import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.auth import AuthUser
# Ensure UserSandbox is imported so that relationship definitions in AuthUser can be resolved
from app.models.user_sandbox import UserSandbox

async def set_admin(email: str):
    print(f"Attempting to set admin privileges for: {email}")
    async with async_session_factory() as session:
        # Check if user exists
        stmt = select(AuthUser).where(AuthUser.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            print(f"Error: User with email '{email}' not found.")
            return

        if user.is_super_user:
            print(f"User '{email}' is already an admin.")
            return

        # Update user
        user.is_super_user = True
        await session.commit()
        print(f"Successfully promoted '{email}' to admin.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/set_admin.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    asyncio.run(set_admin(email))
