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
        self._load_errors = []
        self._load_directory(self.custom_dir, "custom")
        self._load_directory(self.installed_dir, "installed")

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
        for name, content in list(knowledge.items())[:10]:
            if isinstance(name, str) and isinstance(content, str):
                normalized_knowledge[name[:160]] = content[:5000]

        return {
            "id": skill_id,
            "name": str(data.get("name") or skill_id)[:120],
            "icon": str(data.get("icon") or "⚡")[:8],
            "description": str(data.get("description") or "")[:500],
            "system_prompt": str(data.get("system_prompt") or "")[:12000],
            "source": source,
            "github_url": str(data.get("github_url") or "")[:500],
            "knowledge": normalized_knowledge,
        }

    def list_skills(self):
        fields = ("id", "name", "icon", "description", "source", "github_url")
        return [{field: skill.get(field, "") for field in fields} for skill in self._cache.values()]

    def get_skill(self, skill_id):
        return self._cache.get(skill_id)

    def get_skill_prompt(self):
        if not self._cache:
            return ""
        lines = [
            "## 可用技能",
            "根据用户需求判断是否需要技能。需要时必须先调用 load_skill(skill_id) 读取完整技能指令，再按返回内容执行。",
            "不要声称已使用尚未加载的技能。",
            "",
        ]
        for skill in self._cache.values():
            lines.append(
                f"- `{skill['id']}`：{skill['name']} - {skill['description']}"
            )
        return "\n".join(lines)

    def get_skill_context(self, skill_id, max_chars=12000):
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"技能 '{skill_id}' 不存在")

        sections = [
            f"# {skill['name']}",
            skill.get("description", ""),
            "## 技能指令",
            skill.get("system_prompt", ""),
        ]
        knowledge = skill.get("knowledge") or {}
        if knowledge:
            sections.append("## 知识库")
            for name, content in knowledge.items():
                sections.append(f"### {name}\n{content}")
        return "\n\n".join(part for part in sections if part).strip()[:max_chars]

    def diagnostics(self):
        counts = {"builtin": 0, "custom": 0, "installed": 0}
        for skill in self._cache.values():
            source = skill.get("source")
            if source in counts:
                counts[source] += 1
        return {
            "status": "ok" if not self._load_errors else "degraded",
            "total": len(self._cache),
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
        priority_files = (
            "README.md", "readme.md", "USAGE.md", "usage.md", "GUIDE.md", "guide.md",
            "DOCS.md", "docs.md", "INSTRUCTIONS.md", "instructions.md", "prompt.md",
            "system.md", "context.md",
        )
        for name in priority_files:
            path = skill_dir / name
            if path.is_file():
                content = self._read_text(path)
                if content:
                    knowledge[name] = content

        docs_dir = skill_dir / "docs"
        if docs_dir.is_dir():
            for path in sorted(docs_dir.glob("*.md")):
                if len(knowledge) >= 10:
                    break
                content = self._read_text(path)
                if content:
                    knowledge[f"docs/{path.name}"] = content
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
