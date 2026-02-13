#!/usr/bin/env python3
"""
Auto-load Skills Script
Scans the /app/skills directory and imports detected Skills (containing SKILL.md) into the database.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# Ensure app module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.core.database import AsyncSessionLocal
from app.services.skill_service import SkillService

# Import all models to ensure SQLAlchemy can configure relationships
from app.models import AuthUser as User  # noqa: F401
from app.models.user_sandbox import UserSandbox  # noqa: F401

# Setup logging
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", level="INFO")


def get_skills_dir() -> Optional[Path]:
    """Get Skills directory path (compatible with Docker and local development)"""
    # 1. Docker environment
    docker_path = Path("/app/skills")
    if docker_path.exists():
        return docker_path

    # 2. Local development environment (relative to script: backend/scripts/load_skills.py -> ../../skills)
    # Path(__file__) = backend/scripts/load_skills.py
    # .parent = backend/scripts
    # .parent.parent = backend
    # .parent.parent.parent = root
    local_path = Path(__file__).parent.parent.parent / "skills"
    if local_path.exists():
        return local_path

    # 3. Try skills in current working directory
    cwd_path = Path.cwd() / "skills"
    if cwd_path.exists():
        return cwd_path

    return None


async def load_skills():
    """Scan directory and load Skills"""
    skills_dir = get_skills_dir()
    if not skills_dir:
        logger.warning("Skills directory not found. Checked: /app/skills, ../../skills, ./skills")
        return

    logger.info(f"Scanning for skills in: {skills_dir}")

    loaded_count = 0
    error_count = 0

    async with AsyncSessionLocal() as db:
        service = SkillService(db)

        # Get system admin ID (usually the first user or specific ID; using fixed ID or finding first admin for simplicity)
        # In initialization phase, users might not exist, or default admin is used
        # Assuming a system admin exists or created by system
        # For simplicity, finding an admin user
        from sqlalchemy import select

        # Try to find admin user
        result = await db.execute(select(User).where(User.is_super_user.is_(True)))
        admin = result.scalars().first()

        if not admin:
            # If no admin, try to find any user for skill ownership
            logger.warning("No superuser found. Trying to find any user for skill ownership.")
            result = await db.execute(select(User))
            admin = result.scalars().first()

        if not admin:
            logger.error("No users found in database. Cannot assign skill ownership. Skipping skill loading.")
            logger.error("Please ensure admin user is created before loading skills.")
            return

        owner_id = str(admin.id)
        logger.info(f"Importing skills as user: {admin.email} ({owner_id})")

        # Iterate first-level subdirectories
        for item in skills_dir.iterdir():
            if item.is_dir():
                skill_dir = item
                skill_md_path = skill_dir / "SKILL.md"

                if not skill_md_path.exists():
                    # Try finding lowercase skill.md
                    skill_md_path = skill_dir / "skill.md"

                if skill_md_path.exists():
                    try:
                        await import_single_skill(service, skill_dir, skill_md_path, owner_id)
                        loaded_count += 1
                    except Exception as e:
                        logger.error(f"Failed to import skill from {skill_dir}: {e}")
                        error_count += 1
                else:
                    # Recursively check subdirectories (e.g. skills/python/SKILL.md)
                    # Simple second-level depth check
                    has_skill = False
                    for subitem in skill_dir.iterdir():
                        if subitem.is_dir():
                            sub_skill_md = subitem / "SKILL.md"
                            if sub_skill_md.exists():
                                try:
                                    await import_single_skill(service, subitem, sub_skill_md, owner_id)
                                    loaded_count += 1
                                    has_skill = True
                                except Exception as e:
                                    logger.error(f"Failed to import skill from {subitem}: {e}")
                                    error_count += 1

                    if not has_skill:
                        logger.debug(f"Skipping {skill_dir}: No SKILL.md found")

    logger.info(f"Skill loading complete. Loaded: {loaded_count}, Errors: {error_count}")


async def import_single_skill(service: SkillService, skill_dir: Path, skill_md_path: Path, owner_id: str):
    """Import single Skill"""
    logger.info(f"Processing skill: {skill_dir.name}")

    try:
        await service.import_skill_from_directory(str(skill_dir), owner_id, is_public=True)
        logger.info(f"  Successfully imported skill: {skill_dir.name}")
    except Exception as e:
        logger.error(f"  Failed to import skill {skill_dir.name}: {e}")
        raise e


if __name__ == "__main__":
    asyncio.run(load_skills())
