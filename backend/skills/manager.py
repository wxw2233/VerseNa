import json
import os
import re
import shutil
import stat
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse
from config import settings


def _rmtree_readonly(path):
    """删除目录，处理 Windows 只读文件。"""
    def on_rm_error(func, file_path, exc_info):
        os.chmod(file_path, stat.S_IWRITE)
        func(file_path)

    shutil.rmtree(path, onerror=on_rm_error)


SKILLS_DIR = Path(__file__).parent
BUILTIN_DIR = SKILLS_DIR / "builtin"
CUSTOM_DIR = settings.SKILLS_DATA_DIR / "custom"
INSTALLED_DIR = settings.SKILLS_DATA_DIR / "installed"
SKILL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SLASH_COMMAND_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SLASH_INPUT_PATTERN = re.compile(
    r"^\s*/([A-Za-z0-9][A-Za-z0-9._:-]{0,127})(?:\s+([\s\S]*))?$"
)
RESERVED_SLASH_COMMANDS = {"skill"}
MAX_COMMAND_CONTEXT_CHARS = 12000
MAX_SKILL_INDEX_CHARS = 7000
MAX_SKILL_INDEX_DESCRIPTION_CHARS = 120
MAX_ROOT_SKILL_CONTEXT_CHARS = 6000
MAX_KNOWLEDGE_FILES = 3
MAX_KNOWLEDGE_FILE_CHARS = 3000
EXCLUDED_KNOWLEDGE_DIRECTORIES = {"docs", "tests", ".github", "examples"}
KNOWLEDGE_BASENAMES = {
    "readme.md", "readme.rst", "readme.txt", "readme",
    "usage.md", "guide.md", "instructions.md", "prompt.md",
    "system.md", "context.md",
}
COMMAND_HINTS = {
    "brainstorming": "脑暴 头脑风暴 需求探索 澄清想法",
    "writing-plans": "制定计划 实施计划 任务计划",
    "executing-plans": "执行计划 实施方案",
    "systematic-debugging": "系统调试 排查问题 根因分析",
    "test-driven-development": "测试驱动 TDD 先写测试",
    "verification-before-completion": "完成前验证 验收 检查结果",
    "requesting-code-review": "请求代码审查 review",
    "receiving-code-review": "处理代码审查意见",
    "subagent-driven-development": "子代理驱动开发 委派实现",
}

BUILTIN_SKILLS = [
    {
        "id": "translator",
        "name": "翻译专家",
        "icon": "🌐",
        "description": "将文本翻译为指定语言，支持多语种互译",
        "system_prompt": "你是一个专业翻译专家。请将用户输入的内容翻译为指定的语言。如果用户没有指定目标语言，请翻译为英文。翻译时注意：1. 保持原文的语气和风格 2. 专业术语要准确 3. 必要时提供多种翻译方案 4. 简要说明翻译要点。",
        "source": "builtin",
    },
    {
        "id": "writer",
        "name": "写作助手",
        "icon": "📝",
        "description": "文案润色、文章改写、创意写作",
        "system_prompt": "你是一个专业写作助手。请帮助用户润色、改写或创作文本。注意：1. 保持用户的原始意图 2. 优化语言表达和逻辑结构 3. 提供修改建议和理由 4. 根据场景调整语气风格。",
        "source": "builtin",
    },
    {
        "id": "coder",
        "name": "代码助手",
        "icon": "💻",
        "description": "代码审查、Bug 修复、架构建议",
        "system_prompt": "你是一个资深软件工程师。请帮助用户审查代码、修复 Bug 或提供架构建议。注意：1. 指出潜在问题和安全隐患 2. 提供优化后的代码 3. 解释修改原因 4. 遵循最佳实践。",
        "source": "builtin",
    },
    {
        "id": "searcher",
        "name": "搜索增强",
        "icon": "🔍",
        "description": "优先使用搜索引擎获取最新信息",
        "system_prompt": "你是一个信息检索专家。对于用户的问题，请优先使用搜索工具获取最新、最准确的信息。注意：1. 搜索时使用精准关键词 2. 综合多个来源 3. 标注信息来源。",
        "source": "builtin",
    },
    {
        "id": "analyst",
        "name": "数据分析",
        "icon": "📊",
        "description": "数据解读、统计分析、可视化建议",
        "system_prompt": "你是一个数据分析专家。请帮助用户分析数据、解读趋势、提供可视化建议。注意：1. 先理解数据的背景和含义 2. 使用合适的统计方法 3. 用通俗语言解释分析结果。",
        "source": "builtin",
    },
]


class SkillManager:
    def __init__(self, installed_dir=None, custom_dir=None):
        self.installed_dir = Path(installed_dir or INSTALLED_DIR)
        self.custom_dir = Path(custom_dir or CUSTOM_DIR)
        self.installed_dir.mkdir(parents=True, exist_ok=True)
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}
        self._skill_dirs = {}
        self._load_errors = []
        self._load_all()

    def _load_all(self):
        self._cache = {skill["id"]: dict(skill) for skill in BUILTIN_SKILLS}
        self._skill_dirs = {}
        self._commands = {}
        self._command_aliases = {}
        self._load_errors = []
        self._load_directory(self.custom_dir, "custom")
        self._load_directory(self.installed_dir, "installed")
        for skill in self._cache.values():
            self._register_root_command(skill)
        for skill_id, directory in self._skill_dirs.items():
            self._discover_commands(skill_id, directory)

    def _load_directory(self, root, source):
        for directory in sorted(root.iterdir()):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            skill_json = directory / "skill.json"
            if not skill_json.exists():
                self._load_errors.append(f"{source}/{directory.name}: 缺少 skill.json")
                continue
            try:
                raw = json.loads(skill_json.read_text(encoding="utf-8"))
                skill = self._normalize_skill(raw, directory.name, source)
                if skill["id"] in self._cache:
                    raise ValueError(f"技能 ID '{skill['id']}' 与现有技能冲突")
                self._cache[skill["id"]] = skill
                self._skill_dirs[skill["id"]] = directory
            except Exception as exc:
                self._load_errors.append(f"{source}/{directory.name}: {exc}")

    def _normalize_skill(self, data, default_id, source):
        if not isinstance(data, dict):
            raise ValueError("skill.json 必须是对象")
        skill_id = str(data.get("id") or default_id).strip()
        if not SKILL_ID_PATTERN.fullmatch(skill_id):
            raise ValueError("技能 ID 只能包含字母、数字、点、下划线和连字符，且最长 64 字符")

        knowledge = data.get("knowledge") if isinstance(data.get("knowledge"), dict) else {}
        normalized_knowledge = {}
        seen_content = set()
        for name, content in knowledge.items():
            if not isinstance(name, str) or not isinstance(content, str):
                continue
            relative_name = name.replace("\\", "/").strip("/")
            parts = [part.casefold() for part in relative_name.split("/") if part]
            if not relative_name or (parts and parts[0] in EXCLUDED_KNOWLEDGE_DIRECTORIES):
                continue
            basename = Path(relative_name).name.casefold()
            if basename not in KNOWLEDGE_BASENAMES:
                continue
            # Treat README.md/readme.md and equivalent casing as one logical
            # document. This fixes repositories that were scanned on a
            # case-sensitive filesystem and then loaded twice on Windows.
            if basename.startswith("readme"):
                relative_name = "README.md"
            elif basename in {"usage.md", "guide.md", "instructions.md", "prompt.md", "system.md", "context.md"}:
                relative_name = basename
            normalized_content = content.strip()
            content_key = normalized_content.casefold()
            if not normalized_content or content_key in seen_content or relative_name in normalized_knowledge:
                continue
            seen_content.add(content_key)
            normalized_knowledge[relative_name[:160]] = normalized_content[:MAX_KNOWLEDGE_FILE_CHARS]
            if len(normalized_knowledge) >= MAX_KNOWLEDGE_FILES:
                break

        normalized_commands = []
        raw_commands = data.get("commands")
        if isinstance(raw_commands, dict):
            raw_commands = [
                {"name": name, **(value if isinstance(value, dict) else {"prompt": value})}
                for name, value in raw_commands.items()
            ]
        if isinstance(raw_commands, list):
            for item in raw_commands[:50]:
                if isinstance(item, str):
                    item = {"name": item}
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                normalized_commands.append({
                    "name": name[:64],
                    "description": str(item.get("description") or "")[:500],
                    "path": str(item.get("path") or "")[:300],
                    "prompt": str(item.get("prompt") or "")[:MAX_COMMAND_CONTEXT_CHARS],
                })

        def metadata_list(*keys, limit=12, item_limit=300):
            values = []
            for key in keys:
                raw = data.get(key)
                if isinstance(raw, str):
                    raw = [raw]
                if not isinstance(raw, (list, tuple)):
                    continue
                for item in raw:
                    value = str(item or "").strip()[:item_limit]
                    if value and value not in values:
                        values.append(value)
                    if len(values) >= limit:
                        return values
            return values

        return {
            "id": skill_id,
            "name": str(data.get("name") or skill_id)[:120],
            "icon": str(data.get("icon") or "⚡")[:8],
            "description": str(data.get("description") or "")[:500],
            "system_prompt": str(data.get("system_prompt") or "")[:12000],
            "source": source,
            "github_url": str(data.get("github_url") or "")[:500],
            "knowledge": normalized_knowledge,
            "commands": normalized_commands,
            "applies_when": metadata_list("applies_when", "when_to_use", "triggers"),
            "not_applicable_when": metadata_list("not_applicable_when", "when_not_to_use", "excludes"),
            "requires_load": bool(data.get("requires_load", True)),
            "output_constraints": metadata_list("output_constraints", "output_requirements"),
            "tool_permissions": metadata_list("tool_permissions", "allowed_tools"),
        }

    def list_skills(self):
        fields = (
            "id", "name", "icon", "description", "source", "github_url",
            "applies_when", "not_applicable_when", "requires_load",
            "output_constraints", "tool_permissions",
        )
        return [{field: skill.get(field, "") for field in fields} for skill in self._cache.values()]

    @staticmethod
    def _normalize_command_name(value):
        name = str(value or "").strip().lstrip("/").lower()
        return name if SLASH_COMMAND_PATTERN.fullmatch(name) else ""

    @staticmethod
    def _parse_skill_document(content):
        metadata = {}
        body = content
        if content.startswith("---\n") or content.startswith("---\r\n"):
            lines = content.splitlines()
            closing_index = next(
                (index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"),
                None,
            )
            if closing_index is not None:
                for line in lines[1:closing_index]:
                    key, separator, value = line.partition(":")
                    if not separator or key.strip() not in {"name", "description"}:
                        continue
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                        value = value[1:-1]
                    metadata[key.strip()] = value
                body = "\n".join(lines[closing_index + 1:]).strip()
        return metadata, body

    @staticmethod
    def _public_command(command):
        fields = (
            "command",
            "name",
            "description",
            "skill_id",
            "skill_name",
            "source",
            "aliases",
        )
        return {field: command.get(field, "") for field in fields}

    def _register_command(
        self,
        skill_id,
        name,
        description,
        context,
        *,
        kind="command",
        routing_description="",
    ):
        name = self._normalize_command_name(name)
        if not name:
            return
        skill = self._cache.get(skill_id)
        if not skill:
            return

        qualified_name = f"{skill_id}:{name}".lower()
        command_name = name
        if command_name in RESERVED_SLASH_COMMANDS or command_name in self._command_aliases:
            command_name = qualified_name
        if command_name in self._command_aliases:
            self._load_errors.append(
                f"{skill_id}: slash command '{name}' conflicts with another installed skill"
            )
            return

        aliases = []
        if qualified_name != command_name:
            aliases.append(qualified_name)
        command = {
            "command": command_name,
            "name": name,
            "description": str(description or skill.get("description") or "")[:500],
            "skill_id": skill_id,
            "skill_name": skill.get("name", skill_id),
            "source": skill.get("source", "installed"),
            "aliases": aliases,
            "context": str(context or "")[:MAX_COMMAND_CONTEXT_CHARS],
            "routing_description": str(routing_description or "")[:500],
            "kind": kind,
        }
        self._commands[command_name] = command
        self._command_aliases[command_name] = command_name
        self._command_aliases[qualified_name] = command_name

    def _register_root_command(self, skill):
        skill_id = skill.get("id", "")
        self._register_command(
            skill_id,
            skill_id,
            skill.get("description", ""),
            "",
            kind="skill",
            routing_description=skill.get("description", ""),
        )

    def _command_document(self, path):
        content = self._read_text(path, max_len=MAX_COMMAND_CONTEXT_CHARS)
        if not content:
            return {}, ""
        return self._parse_skill_document(content)

    def _discover_commands(self, skill_id, skill_dir):
        skill = self._cache.get(skill_id) or {}
        root = skill_dir.resolve()
        seen_paths = set()

        for spec in skill.get("commands") or []:
            name = spec.get("name", "")
            description = spec.get("description", "")
            context = spec.get("prompt", "")
            relative_path = spec.get("path", "")
            if relative_path:
                path = (root / relative_path).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    self._load_errors.append(
                        f"{skill_id}: slash command path is invalid: {relative_path}"
                    )
                    continue
                metadata, file_context = self._command_document(path)
                seen_paths.add(path)
                name = name or metadata.get("name") or path.parent.name
                routing_description = description or metadata.get("description", "")
                description = routing_description
                context = context or file_context
            if context:
                self._register_command(
                    skill_id,
                    name,
                    description,
                    context,
                    routing_description=routing_description if relative_path else description,
                )

        patterns = (
            "skills/*/SKILL.md",
            ".agents/skills/*/SKILL.md",
            ".codex/skills/*/SKILL.md",
            "commands/**/*.md",
            ".claude/commands/**/*.md",
        )
        for pattern in patterns:
            for path in sorted(root.glob(pattern)):
                resolved = path.resolve()
                if resolved in seen_paths or not resolved.is_relative_to(root):
                    continue
                seen_paths.add(resolved)
                metadata, context = self._command_document(resolved)
                if not context:
                    continue
                default_name = path.parent.name if path.name.lower() == "skill.md" else path.stem
                name = metadata.get("name") or default_name
                routing_description = metadata.get("description", "")
                description = routing_description or self._extract_description(context)
                self._register_command(
                    skill_id,
                    name,
                    description,
                    context,
                    routing_description=routing_description,
                )

    def list_commands(self):
        return [
            self._public_command(command)
            for command in sorted(self._commands.values(), key=lambda item: item["command"])
        ]

    def get_command(self, command_name):
        lookup = str(command_name or "").strip().lstrip("/").lower()
        canonical = self._command_aliases.get(lookup)
        return self._commands.get(canonical) if canonical else None

    def resolve_slash_command(self, content):
        match = SLASH_INPUT_PATTERN.match(str(content or ""))
        if not match:
            return None
        command = self.get_command(match.group(1))
        if not command:
            return None
        return {
            **self._public_command(command),
            "arguments": (match.group(2) or "").strip(),
        }

    def match_natural_language(self, content, *, limit=3):
        """Return high-signal skill routes without injecting full skill text.

        Matching is intentionally a hinting layer. The caller may auto-load a
        single strong match; ambiguous matches are returned for the model to
        resolve rather than turning the whole skill catalog into prompt text.
        """
        text = " ".join(str(content or "").lower().split())
        if not text:
            return []
        candidates = []
        for raw_command in self._commands.values():
            command = self._public_command(raw_command)
            skill = self._cache.get(command.get("skill_id"), {})
            if command.get("command") == command.get("skill_id") and self._child_commands(command.get("skill_id")):
                # A package entry is only a route when the user names its
                # methodology, not for every generic coding request.
                corpus = " ".join([
                    str(skill.get("name") or ""),
                    str(skill.get("description") or ""),
                    " ".join(skill.get("applies_when") or []),
                ]).lower()
            else:
                corpus = " ".join([
                    str(command.get("command") or ""),
                    str(raw_command.get("routing_description") or ""),
                    " ".join(skill.get("applies_when") or []),
                ]).lower()
            hint_text = COMMAND_HINTS.get(command.get("command", ""), "").lower()
            hint_words = list(dict.fromkeys(
                re.findall(r"[a-z0-9_./-]{3,}|[\u4e00-\u9fff]{2,}", hint_text)
            ))
            score = 0
            hits = []
            for phrase in hint_words:
                if phrase in text:
                    score += 6
                    hits.append(phrase)
            words = [word for word in re.findall(r"[a-z0-9_./-]{3,}|[\u4e00-\u9fff]{2,}", corpus)]
            for word in dict.fromkeys(words):
                if word in text:
                    weight = 2 if len(word) >= 5 or re.search(r"[\u4e00-\u9fff]", word) else 1
                    score += weight
                    hits.append(word)
                elif re.search(r"[\u4e00-\u9fff]", word):
                    fragments = {
                        word[index:index + 2]
                        for index in range(max(0, len(word) - 1))
                    }
                    fragment_hits = [fragment for fragment in fragments if fragment in text]
                    if fragment_hits:
                        score += min(3, len(fragment_hits))
                        hits.extend(fragment_hits[:3])
            if command.get("command") in text or skill.get("id", "").lower() in text:
                score += 8
            if score:
                candidates.append({
                    **self._public_command(command),
                    "score": score,
                    "matched_terms": hits[:10],
                    "requires_load": bool(skill.get("requires_load", True)),
                })
        candidates.sort(key=lambda item: (-item["score"], item.get("command", "")))
        return candidates[:max(1, int(limit or 3))]

    @staticmethod
    def select_natural_language_route(matches, *, minimum_score=5, minimum_margin=2):
        """Return one route only when the match is strong and unambiguous."""
        candidates = [item for item in (matches or []) if isinstance(item, dict)]
        if not candidates:
            return None
        top = candidates[0]
        second_score = int(candidates[1].get("score", 0) or 0) if len(candidates) > 1 else 0
        score = int(top.get("score", 0) or 0)
        if score < int(minimum_score) or score < second_score + int(minimum_margin):
            return None
        return top

    def _child_commands(self, skill_id):
        return [
            command for command in self.list_commands()
            if command["skill_id"] == skill_id and command["command"] != skill_id
        ]

    def _render_skill_context(self, skill, max_chars, include_knowledge=True):
        sections = [
            f"# {skill['name']}",
            skill.get("description", ""),
            self._render_skill_metadata(skill),
            "## 技能指令",
            skill.get("system_prompt", ""),
        ]
        knowledge = skill.get("knowledge") or {}
        if include_knowledge and knowledge:
            sections.append("## 知识库")
            for name, content in knowledge.items():
                sections.append(f"### {name}\n{content}")
        return "\n\n".join(part for part in sections if part).strip()[:max_chars]

    @staticmethod
    def _render_skill_metadata(skill):
        lines = ["## 使用边界", "加载后才可将本技能规则用于当前任务。"]
        applies = skill.get("applies_when") or []
        excludes = skill.get("not_applicable_when") or []
        outputs = skill.get("output_constraints") or []
        permissions = skill.get("tool_permissions") or []
        if applies:
            lines.append("适用：" + "；".join(applies[:8]))
        if excludes:
            lines.append("不适用：" + "；".join(excludes[:8]))
        if outputs:
            lines.append("输出约束：" + "；".join(outputs[:8]))
        if permissions:
            lines.append("工具权限：" + "、".join(permissions[:12]))
        return "\n".join(lines)

    def _render_skill_package_context(self, skill, commands, max_chars):
        names = ", ".join(f"`/{command['command']}`" for command in commands)
        sections = [
            f"# {skill['name']}",
            skill.get("description", ""),
            self._render_skill_metadata(skill),
            "## 技能包导航",
            "这是一个包含多个子指令的技能包。不要加载整个仓库文档；应根据用户目标直接使用对应的斜杠指令或调用 load_skill(子指令名)。",
            f"可用子指令：{names}",
        ]
        return "\n\n".join(part for part in sections if part).strip()[:max_chars]

    def get_command_context(self, command_name, max_chars=MAX_COMMAND_CONTEXT_CHARS):
        command = self.get_command(command_name)
        if not command:
            raise ValueError(f"斜杠指令 '{command_name}' 不存在")
        if command.get("kind") == "skill":
            skill = self._cache[command["skill_id"]]
            children = self._child_commands(command["skill_id"])
            if children:
                return self._render_skill_package_context(skill, children, max_chars)
            return self._render_skill_context(skill, max_chars)
        sections = [
            f"# /{command['command']}",
            f"来源技能：{command['skill_name']}",
            command.get("description", ""),
            "## 指令内容",
            command.get("context", ""),
        ]
        return "\n\n".join(part for part in sections if part).strip()[:max_chars]

    def get_skill(self, skill_id):
        return self._cache.get(skill_id)

    @staticmethod
    def _summarize_index_description(description, limit=MAX_SKILL_INDEX_DESCRIPTION_CHARS):
        text = " ".join(str(description or "").split())
        if len(text) <= limit:
            return text

        # Prefer a complete clause, then a word boundary. Never leave a cut-off word.
        cutoff = max(1, limit - 3)
        boundaries = [
            match.end()
            for match in re.finditer(r"[。！？!?；;，,:]", text[:cutoff])
            if match.end() >= cutoff // 2
        ]
        if boundaries:
            return text[:boundaries[-1]].rstrip("，,；;：:") + "..."
        if " " in text[:cutoff]:
            return text[:cutoff].rsplit(" ", 1)[0].rstrip("，,；;：:") + "..."
        return text[:cutoff].rstrip("，,；;：:") + "..."

    def get_skill_prompt(self, max_chars=MAX_SKILL_INDEX_CHARS):
        if not self._cache:
            return ""
        lines = [
            "## 技能索引",
            "用户输入 `/指令` 时直接使用对应路由。自然语言仅在唯一且高度匹配时才主动加载；需要时调用 load_skill(skill_id) 读取完整指令。",
            "不要声称已使用尚未加载的技能。",
            "只有 record_skill_usage 成功后，才能将技能记录为本轮实际采用。",
            "不要逐个枚举或比较候选技能；不明确时直接处理用户请求。",
            "",
        ]
        command_counts = {skill_id: 0 for skill_id in self._cache}
        for command in self.list_commands():
            if command["command"] != command["skill_id"]:
                command_counts[command["skill_id"]] = command_counts.get(command["skill_id"], 0) + 1

        entries = []
        for skill in self._cache.values():
            description = self._summarize_index_description(skill.get("description"))
            command_count = command_counts.get(skill["id"], 0)
            entry = (
                f"- `{skill['id']}`: {skill['name']}"
                + (f" - {description}" if description else "")
            )
            if command_count:
                entry += f"（含 {command_count} 个斜杠指令，可在斜杠菜单中选择）"
            entries.append(entry)

        limit = max(500, int(max_chars or MAX_SKILL_INDEX_CHARS))
        for index, entry in enumerate(entries):
            if len("\n".join(lines + [entry])) > limit:
                remaining = len(entries) - index
                lines.append(f"- 其余 {remaining} 条技能路由未注入当前上下文，可在斜杠菜单中查看。")
                break
            lines.append(entry)
        return "\n".join(lines)

    def get_skill_context(self, skill_id, max_chars=12000):
        skill = self.get_skill(skill_id)
        if skill:
            children = self._child_commands(skill_id)
            if children:
                return self._render_skill_package_context(skill, children, max_chars)
            return self._render_skill_context(
                skill,
                min(max_chars, MAX_ROOT_SKILL_CONTEXT_CHARS),
            )
        command = self.get_command(skill_id)
        if command:
            return self.get_command_context(skill_id, max_chars=max_chars)
        raise ValueError(f"技能或指令 '{skill_id}' 不存在")

    def diagnostics(self):
        counts = {"builtin": 0, "custom": 0, "installed": 0}
        for skill in self._cache.values():
            source = skill.get("source")
            if source in counts:
                counts[source] += 1
        return {
            "status": "ok" if not self._load_errors else "degraded",
            "total": len(self._cache),
            "commands": len(self._commands),
            "counts": counts,
            "load_errors": list(self._load_errors),
        }

    def install_from_github(self, url):
        try:
            repo_name = self._github_repo_name(url)
        except ValueError as exc:
            return None, str(exc)

        target_dir = self.installed_dir / repo_name
        temp_dir = self.installed_dir / f".{repo_name}-{uuid.uuid4().hex}.tmp"
        backup_dir = self.installed_dir / f".{repo_name}-{uuid.uuid4().hex}.bak"

        try:
            result = subprocess.run(
                ["git", "clone", "--depth=1", url, str(temp_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return None, f"克隆失败: {result.stderr[:200]}"

            git_dir = temp_dir / ".git"
            if git_dir.exists():
                _rmtree_readonly(git_dir)

            data = self._prepare_skill(temp_dir, repo_name, url)
            normalized = self._normalize_skill(data, repo_name, "installed")
            existing_dir = self._skill_dirs.get(normalized["id"])
            if normalized["id"] in {skill["id"] for skill in BUILTIN_SKILLS}:
                return None, f"技能 ID '{normalized['id']}' 与内置技能冲突"
            if existing_dir and existing_dir.resolve() != target_dir.resolve():
                return None, f"技能 ID '{normalized['id']}' 已被其他技能使用"

            (temp_dir / "skill.json").write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            if target_dir.exists():
                target_dir.rename(backup_dir)
            try:
                temp_dir.rename(target_dir)
            except Exception:
                if backup_dir.exists() and not target_dir.exists():
                    backup_dir.rename(target_dir)
                raise
            if backup_dir.exists():
                _rmtree_readonly(backup_dir)

            self._load_all()
            return self.get_skill(normalized["id"]), None
        except subprocess.TimeoutExpired:
            return None, "克隆超时"
        except FileNotFoundError:
            return None, "git 未安装"
        except Exception as exc:
            return None, f"安装失败: {exc}"
        finally:
            if temp_dir.exists():
                _rmtree_readonly(temp_dir)

    def _github_repo_name(self, url):
        parsed = urlparse(str(url).strip())
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"github.com", "www.github.com"}
            or parsed.username
            or parsed.password
            or parsed.port
            or parsed.query
            or parsed.fragment
            or len(parts) != 2
            or not SKILL_ID_PATTERN.fullmatch(parts[0])
        ):
            raise ValueError("仅支持 https://github.com/<owner>/<repo> 格式的仓库地址")
        repo_name = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
        if not SKILL_ID_PATTERN.fullmatch(repo_name):
            raise ValueError("GitHub 仓库名称不适合作为安装目录")
        return repo_name

    def _prepare_skill(self, skill_dir, repo_name, url):
        skill_json = skill_dir / "skill.json"
        if skill_json.exists():
            data = json.loads(skill_json.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("skill.json 必须是对象")
            data.setdefault("id", repo_name)
            data.setdefault("icon", "⚡")
            declared = data.get("knowledge") if isinstance(data.get("knowledge"), dict) else {}
            data["knowledge"] = {**declared, **self._scan_knowledge(skill_dir)}
        else:
            readme = self._find_readme(skill_dir)
            if not readme:
                raise ValueError("仓库中找不到 skill.json 或 README")
            readme_content = self._read_text(readme)
            if not readme_content:
                raise ValueError("无法读取 README 内容")
            name = self._extract_title(readme_content) or repo_name.replace("-", " ").replace("_", " ").title()
            description = self._extract_description(readme_content)
            data = {
                "id": repo_name,
                "name": name,
                "icon": "📦",
                "description": description,
                "system_prompt": f"你正在使用技能：{name}。请严格参考技能知识库完成相关任务。",
                "knowledge": self._scan_knowledge(skill_dir),
            }
        data["github_url"] = url
        return data

    def _find_readme(self, directory):
        for name in ("README.md", "readme.md", "README.rst", "README.txt", "README"):
            path = directory / name
            if path.is_file():
                return path
        return None

    def _read_text(self, path, max_len=5000):
        try:
            resolved = path.resolve()
            allowed_roots = (self.installed_dir.resolve(), self.custom_dir.resolve())
            if not any(resolved.is_relative_to(root) for root in allowed_roots):
                return ""
            return path.read_text(encoding="utf-8", errors="replace")[:max_len]
        except Exception:
            return ""

    def _extract_title(self, content):
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    def _extract_description(self, content):
        found_title = False
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                found_title = True
                continue
            if found_title and not line.startswith(("!", "-", "*", ">", "```", "|")):
                return line[:300]
        return content[:200].replace("\n", " ")

    def _scan_knowledge(self, skill_dir):
        knowledge = {}
        seen_paths = set()
        seen_names = set()
        priority_files = (
            "README.md", "readme.md", "USAGE.md", "usage.md", "GUIDE.md", "guide.md",
            "DOCS.md", "docs.md", "INSTRUCTIONS.md", "instructions.md", "prompt.md",
            "system.md", "context.md",
        )
        for name in priority_files:
            path = skill_dir / name
            resolved = path.resolve()
            canonical_name = "README.md" if name.casefold().startswith("readme") else name.casefold()
            if canonical_name in seen_names:
                continue
            if path.is_file() and resolved not in seen_paths:
                seen_paths.add(resolved)
                content = self._read_text(path)
                if content:
                    knowledge[canonical_name] = content[:MAX_KNOWLEDGE_FILE_CHARS]
                    seen_names.add(canonical_name)
            if len(knowledge) >= MAX_KNOWLEDGE_FILES:
                break
        return knowledge

    def delete_skill(self, skill_id):
        skill = self._cache.get(skill_id)
        if not skill:
            raise ValueError(f"技能 '{skill_id}' 不存在")
        if skill.get("source") == "builtin":
            raise ValueError("不能删除内置技能")

        skill_dir = self._skill_dirs.get(skill_id)
        if not skill_dir:
            raise ValueError("找不到技能安装目录")
        allowed_roots = (self.installed_dir.resolve(), self.custom_dir.resolve())
        resolved = skill_dir.resolve()
        if not any(resolved.parent == root for root in allowed_roots):
            raise ValueError("技能目录不安全")
        _rmtree_readonly(skill_dir)
        self._load_all()

    def reload(self):
        self._load_all()


skill_manager = SkillManager()
