from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from loguru import logger

from app.core.database import AsyncSessionLocal
from app.services.skill_service import SkillService


# Logic to get Skills directory (reuse logic from scripts/load_skills.py)
def get_skills_dir() -> Optional[Path]:
    """Get Skills directory path (compatible with Docker and local development)"""
    # 1. Docker environment
    docker_path = Path("/app/skills")
    if docker_path.exists():
        return docker_path

    # 2. Local development environment (try to find from current working directory)
    # Assume current working directory is backend/
    cwd_path = Path.cwd() / "skills"
    if cwd_path.exists():
        return cwd_path

    # 3. Relative path backtracking
    # If currently in backend/app/core/skill_developer_deepagents/tools.py
    # .parent.parent.parent.parent.parent / "skills"
    local_path = Path(__file__).parent.parent.parent.parent.parent / "skills"
    if local_path.exists():
        return local_path

    return None


@tool
async def deploy_local_skill(skill_name: str, owner_id: str = "") -> str:
    """
    Deploy a locally generated Skill to the database (private).

    Usage scenario: When an Agent creates SKILL.md and code files in the local `skills/<skill_name>` directory,
    call this tool to register it in the system. Skill defaults to private, visible only to owner.

    Args:
        skill_name: Directory name of the Skill (e.g. "my_new_tool")
        owner_id: Current user ID, used to set the owner of the Skill

    Returns:
        Deployment result message
    """
    if not owner_id:
        return "Error: owner_id is required. Please provide the current user's ID."

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

            skill = await service.import_skill_from_directory(str(skill_dir), owner_id, is_public=False)
            return f"Success: Skill '{skill.name}' (ID: {skill.id}) deployed as private skill."

    except Exception as e:
        logger.error(f"Failed to deploy skill {skill_name}: {e}")
        return f"Error deploying skill: {str(e)}"
