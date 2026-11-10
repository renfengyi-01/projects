# -*- coding: utf-8 -*-
"""技能（Skill）管理：扫描技能目录、渐进加载、按需读取技能内容。

技能落盘约定：
    <workdir>/skills/<skill-name>/SKILL.md
其中 SKILL.md 顶部必须有 YAML frontmatter：
    ---
    name: my-skill
    description: 一句话说明这个技能做什么
    ---
    （正文：详细步骤/知识）

- 启动时只扫描 name+description 注入系统提示（渐进加载），不读正文。
- 模型需要时调用 read_skill 工具按需读取正文，正文有长度上限。
- 技能名只允许小写字母/数字/连字符，拒绝与已有技能重名。
"""
from __future__ import annotations

import re
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
_MAX_SKILL_BODY = 12000


class Skill:
    def __init__(self, name: str, description: str, path: Path, body: str = ""):
        self.name = name
        self.description = description
        self.path = path
        self._body = body

    @property
    def body(self) -> str:
        if not self._body:
            try:
                self._body = self.path.read_text(encoding="utf-8")
            except OSError as exc:
                self._body = f"（读取技能失败: {exc}）"
        return self._body


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    body = text[m.end():]
    return meta, body


class SkillsManager:
    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}

    def scan(self) -> None:
        """扫描技能目录，只解析 frontmatter 的 name/description，不读正文。"""
        self.skills.clear()
        if not self.skills_dir.exists():
            return
        for entry in sorted(self.skills_dir.iterdir()):
            skill_md = entry / "SKILL.md"
            if not entry.is_dir() or not skill_md.is_file():
                continue
            try:
                text = skill_md.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, _ = _parse_frontmatter(text)
            name = meta.get("name") or entry.name
            if not _NAME_RE.match(name):
                continue
            desc = meta.get("description", "").strip()
            self.skills[name] = Skill(name=name, description=desc, path=skill_md)

    def list_summary(self) -> list[dict]:
        """返回 name+description 列表，用于注入系统提示。"""
        return [{"name": s.name, "description": s.description} for s in self.skills.values()]

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def read_body(self, name: str) -> str:
        skill = self.skills.get(name)
        if skill is None:
            return f"技能 '{name}' 不存在。可用技能: {', '.join(self.skills) or '无'}"
        body = skill.body
        if len(body) > _MAX_SKILL_BODY:
            body = body[:_MAX_SKILL_BODY] + f"\n...（截断，原文 {len(body)} 字符）"
        return body

    def create_skill(self, name: str, description: str, body: str = "") -> dict:
        """创建新技能目录 + SKILL.md。拒绝重名、拒绝非法命名。"""
        if not _NAME_RE.match(name):
            return {"ok": False, "error": "技能名只允许小写字母/数字/连字符，且以字母或数字开头"}
        if name in self.skills:
            return {"ok": False, "error": f"技能 '{name}' 已存在，拒绝覆盖"}
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(exist_ok=False)
        content = (
            f"---\nname: {name}\ndescription: {description}\n---\n\n"
            f"{body or '# ' + name + chr(10)}"
        )
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        self.skills[name] = Skill(name=name, description=description, path=skill_dir / "SKILL.md")
        return {"ok": True, "name": name, "path": str(skill_dir)}
