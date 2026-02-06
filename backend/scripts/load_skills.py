#!/usr/bin/env python3
"""
自动加载 Skills 脚本
扫描 /app/skills 目录，将检测到的 Skill (含有 SKILL.md) 导入数据库。
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# 确保可以导入 app 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.core.database import AsyncSessionLocal
from app.services.skill_service import SkillService

# 设置日志
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", level="INFO")


def get_skills_dir() -> Optional[Path]:
    """获取 Skills 目录路径（兼容 Docker 和本地开发）"""
    # 1. Docker 环境
    docker_path = Path("/app/skills")
    if docker_path.exists():
        return docker_path

    # 2. 本地开发环境 (相对于脚本位置: backend/scripts/load_skills.py -> ../../skills)
    # Path(__file__) = backend/scripts/load_skills.py
    # .parent = backend/scripts
    # .parent.parent = backend
    # .parent.parent.parent = root
    local_path = Path(__file__).parent.parent.parent / "skills"
    if local_path.exists():
        return local_path

    # 3. 尝试当前工作目录下的 skills
    cwd_path = Path.cwd() / "skills"
    if cwd_path.exists():
        return cwd_path

    return None


async def load_skills():
    """扫描目录并加载 Skills"""
    skills_dir = get_skills_dir()
    if not skills_dir:
        logger.warning("Skills directory not found. Checked: /app/skills, ../../skills, ./skills")
        return

    logger.info(f"Scanning for skills in: {skills_dir}")

    loaded_count = 0
    error_count = 0

    async with AsyncSessionLocal() as db:
        service = SkillService(db)

        # 获取系统管理员 ID (通常是第一个用户或特定 ID，这里为了简化，暂时使用固定 ID 或查找第一个 admin)
        # 在初始化阶段，可能还没有用户，或者使用默认的 admin
        # 这里假设存在一个系统 admin 或者由 system 创建
        # 为了简单起见，我们查找一个 admin 用户
        from sqlalchemy import select

        from app.models.auth import AuthUser as User

        # 尝试查找 admin 用户
        result = await db.execute(select(User).where(User.is_super_user.is_(True)))
        admin = result.scalars().first()

        if not admin:
            # 如果没有管理员，尝试查找任意用户
            logger.warning("No superuser found. Trying to find any user for skill ownership.")
            result = await db.execute(select(User))
            admin = result.scalars().first()

        if not admin:
            logger.error("No users found in database. Cannot assign skill ownership. Skipping skill loading.")
            return

        owner_id = str(admin.id)
        logger.info(f"Importing skills as user: {admin.email} ({owner_id})")

        # 遍历一级子目录
        for item in skills_dir.iterdir():
            if item.is_dir():
                skill_dir = item
                skill_md_path = skill_dir / "SKILL.md"

                if not skill_md_path.exists():
                    # 尝试查找小写的 skill.md
                    skill_md_path = skill_dir / "skill.md"

                if skill_md_path.exists():
                    try:
                        await import_single_skill(service, skill_dir, skill_md_path, owner_id)
                        loaded_count += 1
                    except Exception as e:
                        logger.error(f"Failed to import skill from {skill_dir}: {e}")
                        error_count += 1
                else:
                    # 递归检查子目录 (例如 skills/python/SKILL.md)
                    # 简单的二级深度检查
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
    """导入单个 Skill"""
    logger.info(f"Processing skill: {skill_dir.name}")

    try:
        await service.import_skill_from_directory(str(skill_dir), owner_id)
        logger.info(f"  Successfully imported skill: {skill_dir.name}")
    except Exception as e:
        logger.error(f"  Failed to import skill {skill_dir.name}: {e}")
        raise e


if __name__ == "__main__":
    asyncio.run(load_skills())
