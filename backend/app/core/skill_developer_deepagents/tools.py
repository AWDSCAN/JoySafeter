from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from loguru import logger

from app.core.database import AsyncSessionLocal
from app.services.skill_service import SkillService


# 获取 Skills 目录的逻辑 (复用 scripts/load_skills.py 的逻辑)
def get_skills_dir() -> Optional[Path]:
    """获取 Skills 目录路径（兼容 Docker 和本地开发）"""
    # 1. Docker 环境
    docker_path = Path("/app/skills")
    if docker_path.exists():
        return docker_path

    # 2. 本地开发环境 (尝试从当前工作目录查找)
    # 假设当前工作目录是 backend/
    cwd_path = Path.cwd() / "skills"
    if cwd_path.exists():
        return cwd_path

    # 3. 相对路径回溯
    # 如果当前是在 backend/app/core/skill_developer_deepagents/tools.py
    # .parent.parent.parent.parent.parent / "skills"
    local_path = Path(__file__).parent.parent.parent.parent.parent / "skills"
    if local_path.exists():
        return local_path

    return None


@tool
async def deploy_local_skill(skill_name: str) -> str:
    """
    将本地生成的 Skill 部署到数据库中。

    使用场景：当 Agent 在本地 `skills/<skill_name>` 目录创建了 SKILL.md 和代码文件后，
    调用此工具将其注册到系统。

    Args:
        skill_name: Skill 的目录名称 (例如: "my_new_tool")

    Returns:
        部署结果消息
    """
    skills_root = get_skills_dir()
    if not skills_root:
        return "Error: Could not locate 'skills' directory on the server."

    skill_dir = skills_root / skill_name
    if not skill_dir.exists():
        return f"Error: Skill directory not found: {skill_dir}"

    if not (skill_dir / "SKILL.md").exists() and not (skill_dir / "skill.md").exists():
        return f"Error: SKILL.md not found in {skill_dir}. Please create it first."

    try:
        async with AsyncSessionLocal() as db:
            service = SkillService(db)

            # 获取系统管理员或任意用户作为拥有者
            from sqlalchemy import select

            from app.models.auth import AuthUser as User

            # 尝试查找 admin 用户
            result = await db.execute(select(User).where(User.is_super_user.is_(True)))
            admin = result.scalars().first()

            if not admin:
                # 如果没有管理员，尝试查找任意用户
                result = await db.execute(select(User))
                admin = result.scalars().first()

            if not admin:
                return "Error: No user found in system to assign skill ownership."

            skill = await service.import_skill_from_directory(str(skill_dir), str(admin.id))
            return f"Success: Skill '{skill.name}' (ID: {skill.id}) deployed successfully."

    except Exception as e:
        logger.error(f"Failed to deploy skill {skill_name}: {e}")
        return f"Error deploying skill: {str(e)}"
