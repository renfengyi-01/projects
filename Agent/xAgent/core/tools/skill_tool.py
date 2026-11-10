# -*- coding: utf-8 -*-
"""面向模型的技能操作工具：列出技能、读取技能正文、创建新技能。"""
from __future__ import annotations

from ..skills_manager import SkillsManager
from .base import BaseTool


class ListSkillsTool(BaseTool):
    name = "list_skills"
    description = "列出当前所有可用技能的名称与一句话描述（只返回摘要，不返回正文）。"
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, manager: SkillsManager):
        self.manager = manager

    def execute(self) -> dict:
        items = self.manager.list_summary()
        return {"count": len(items), "skills": items}


class ReadSkillTool(BaseTool):
    name = "read_skill"
    description = "按名称读取一个技能的完整正文（使用方法/步骤/知识）。需要按技能做事时先读它。"
    parameters = {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "技能名"}},
        "required": ["name"],
    }

    def __init__(self, manager: SkillsManager):
        self.manager = manager

    def execute(self, name: str) -> dict:
        body = self.manager.read_body(name)
        return {"name": name, "content": body}


class CreateSkillTool(BaseTool):
    name = "create_skill"
    description = (
        "在 skills/ 目录下创建一个新技能：生成 <name>/SKILL.md（带 YAML frontmatter）。"
        "拒绝重名、拒绝非法命名。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名，小写字母/数字/连字符"},
            "description": {"type": "string", "description": "一句话描述技能用途"},
            "body": {"type": "string", "description": "可选，技能正文（步骤/知识）"},
        },
        "required": ["name", "description"],
    }

    def __init__(self, manager: SkillsManager):
        self.manager = manager

    def execute(self, name: str, description: str, body: str = "") -> dict:
        return self.manager.create_skill(name, description, body)
