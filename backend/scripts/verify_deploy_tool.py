import asyncio
import shutil
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.skill_developer_deepagents.tools import deploy_local_skill


async def verify():
    # Setup test skill
    skill_name = "test_deploy_skill_001"
    skills_dir = Path(__file__).parent.parent / "skills"

    if not skills_dir.exists():
        skills_dir.mkdir()

    test_skill_dir = skills_dir / skill_name
    if test_skill_dir.exists():
        shutil.rmtree(test_skill_dir)
    test_skill_dir.mkdir()

    # Create SKILL.md
    with open(test_skill_dir / "SKILL.md", "w") as f:
        f.write("""---
name: test_deploy_skill_001
description: A test skill for verification.
---
# Test Skill
This is a test skill.
""")

    # Create dummy python file
    with open(test_skill_dir / "test.py", "w") as f:
        f.write("def hello():\n    print('Hello World')")

    print(f"Created test skill at {test_skill_dir}")

    # Run tool
    print("Running deploy_local_skill...")
    # Function called directly might need invoke or just call the func if it's decorated but accessible
    # Langchain @tool decorates the function. The original function is usually available as .func ??
    # Or we can just call it if it's a coroutine.
    # Let's try calling it.
    try:
        result = await deploy_local_skill.ainvoke(skill_name)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error calling tool: {e}")
        # Try direct call if ainvoke fails/misses context
        try:
            result = await deploy_local_skill(skill_name)  # Depending on langchain version
            print(f"Result (direct): {result}")
        except Exception as e2:
            print(f"Error calling tool directly: {e2}")

    # Cleanup
    # shutil.rmtree(test_skill_dir)


if __name__ == "__main__":
    # Ensure env vars are loaded (simplified)
    # create .env if needed or assume environment is set
    asyncio.run(verify())
