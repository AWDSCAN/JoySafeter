#!/usr/bin/env python3
"""
自动加载 Skills 脚本
扫描 /app/skills 目录，将检测到的 Skill (含有 SKILL.md) 导入数据库。
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

# 确保可以导入 app 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.services.skill_service import SkillService
from app.core.skill.yaml_parser import parse_skill_md, extract_metadata_from_frontmatter
from loguru import logger

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
        from app.models.auth import AuthUser as User
        from sqlalchemy import select
        
        # 尝试查找 admin 用户
        result = await db.execute(select(User).where(User.is_superuser == True))
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
    
    # 读取 SKILL.md
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 解析元数据
    frontmatter, body = parse_skill_md(content)
    metadata = extract_metadata_from_frontmatter(frontmatter)
    
    name = metadata.get("name", skill_dir.name)
    description = metadata.get("description", "")
    
    # 准备文件列表
    files = []
    
    # 添加 SKILL.md
    files.append({
        "path": "SKILL.md",
        "file_name": "SKILL.md",
        "content": content,
        "file_type": "markdown"
    })
    
    # 添加目录下的其他文件 (递归)
    for file_path in skill_dir.rglob("*"):
        if file_path.is_file() and file_path.name != "SKILL.md" and not file_path.name.startswith("."):
            try:
                 # 计算相对路径
                rel_path = file_path.relative_to(skill_dir)
                
                # 读取文件内容 (仅支持文本文件，二进制文件暂时跳过或需要特殊处理)
                # SkillService 目前主要支持文本文件，二进制文件可能会报错
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                        
                    files.append({
                        "path": str(rel_path),
                        "file_name": file_path.name,
                        "content": file_content,
                        "file_type": detect_file_type(file_path)
                    })
                except UnicodeDecodeError:
                    logger.warning(f"  Skipping binary file: {rel_path}")
            except Exception as e:
                logger.warning(f"  Error reading file {file_path}: {e}")

    # 检查 Skill 是否存在
    existing_skill = await service.get_skill_by_name(name, current_user_id=owner_id)
    
    if existing_skill:
        logger.info(f"  Updating existing skill: {name}")
        await service.update_skill(
            skill_id=existing_skill.id,
            current_user_id=owner_id,
            name=name,
            description=description,
            files=files,
            is_public=True # 默认公开？
        )
    else:
        logger.info(f"  Creating new skill: {name}")
        await service.create_skill(
            created_by_id=owner_id,
            name=name,
            description=description,
            content=body,
            files=files,
            owner_id=owner_id,
            is_public=True
        )

def detect_file_type(file_path: Path) -> str:
    """简单检测文件类型"""
    suffix = file_path.suffix.lower()
    if suffix == ".py":
        return "python"
    elif suffix == ".md":
        return "markdown"
    elif suffix == ".json":
        return "json"
    elif suffix == ".yaml" or suffix == ".yml":
        return "yaml"
    elif suffix == ".txt":
        return "text"
    else:
        return "text"

if __name__ == "__main__":
    asyncio.run(load_skills())
