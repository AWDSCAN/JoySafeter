from pathlib import Path
from typing import Any, List

from loguru import logger

from app.core.database import AsyncSessionLocal
from app.core.tools.toolkit import Toolkit
from app.services.skill_service import SkillService


class SkillManagementTools(Toolkit):
    def __init__(self, user_id: str, **kwargs):
        self.user_id = user_id
        # Host path where sandbox volume is mounted
        # Container: /workspace/skills -> Host: /tmp/sandboxes/{user_id}/skills
        self.sandbox_root = Path(f"/tmp/sandboxes/{user_id}")
        self.skills_dir = self.sandbox_root / "skills"

        tools: List[Any] = [self.deploy_local_skill]
        super().__init__(name="skill_management", tools=tools, **kwargs)

    async def deploy_local_skill(self, skill_name: str) -> str:
        """
        Deploy a locally created skill (in sandbox) to the system.

        The skill must be located in `skills/<skill_name>` within the sandbox workspace.
        This tool registers it in the database as a private skill for the current user.

        Args:
            skill_name: The directory name of the skill (e.g., "my_new_tool")

        Returns:
            Success or error message.
        """
        # 1. Locate the skill directory on Host
        skill_dir = self.skills_dir / skill_name

        if not skill_dir.exists():
            # Try checking if it's in the root or other common paths if needed,
            # but standard convention is /workspace/skills
            return f"Error: Skill directory not found in sandbox: skills/{skill_name}"

        # 2. Check for SKILL.md
        if not (skill_dir / "SKILL.md").exists() and not (skill_dir / "skill.md").exists():
            return f"Error: SKILL.md not found in skills/{skill_name}. Please create it first."

        try:
            async with AsyncSessionLocal() as db:
                service = SkillService(db)

                # 3. Import as private skill
                skill = await service.import_skill_from_directory(str(skill_dir), self.user_id, is_public=False)
                return f"Success: Skill '{skill.name}' (ID: {skill.id}) deployed successfully."

        except Exception as e:
            logger.error(f"Failed to deploy skill {skill_name}: {e}")
            return f"Error deploying skill: {str(e)}"
