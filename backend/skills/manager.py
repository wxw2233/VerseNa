import json
import shutil
import subprocess
import stat
from pathlib import Path


def _rmtree_readonly(path):
    """删除目录，处理 Windows 只读文件"""
    def on_rm_error(func, fpath, exc_info):
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)
    import os
    shutil.rmtree(path, onerror=on_rm_error)

SKILLS_DIR = Path(__file__).parent
BUILTIN_DIR = SKILLS_DIR / "builtin"
INSTALLED_DIR = SKILLS_DIR / "installed"

# 内置技能
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
    def __init__(self):
        INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
        self._cache = {}
        self._load_all()

    def _load_all(self):
        self._cache = {}
        for skill in BUILTIN_SKILLS:
            self._cache[skill["id"]] = skill
        for d in INSTALLED_DIR.iterdir():
            if d.is_dir():
                skill_json = d / "skill.json"
                if skill_json.exists():
                    try:
                        data = json.loads(skill_json.read_text(encoding="utf-8"))
                        data["source"] = "installed"
                        self._cache[data.get("id", d.name)] = data
                    except Exception:
                        pass

    def list_skills(self):
        return list(self._cache.values())

    def get_skill(self, skill_id):
        return self._cache.get(skill_id)

    def get_skill_prompt(self):
        """生成技能列表提示词（注入 system prompt）"""
        skills = self.list_skills()
        if not skills:
            return ""
        lines = [
            "## 可用技能",
            "根据用户的消息内容，自动判断是否需要使用某个技能。",
            "如果使用了某个技能，在回复中简要说明。",
            "",
        ]
        for s in skills:
            lines.append(f"- **{s['name']}** ({s['icon']}): {s['description']}")
            # 如果有知识库，注入摘要
            knowledge = s.get("knowledge", {})
            if knowledge:
                # 只取第一个文件的前500字作为摘要
                first_content = list(knowledge.values())[0][:500]
                lines.append(f"  知识库摘要: {first_content[:200]}...")
            if s.get("system_prompt"):
                lines.append(f"  技能指令: {s['system_prompt'][:300]}")
            lines.append("")
        return "\n".join(lines)

    def install_from_github(self, url):
        """从 GitHub 仓库安装技能"""
        repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
        skill_dir = INSTALLED_DIR / repo_name

        if skill_dir.exists():
            _rmtree_readonly(skill_dir)

        # 克隆仓库
        try:
            result = subprocess.run(
                ["git", "clone", "--depth=1", url, str(skill_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return None, f"克隆失败: {result.stderr[:200]}"
        except subprocess.TimeoutExpired:
            return None, "克隆超时"
        except FileNotFoundError:
            return None, "git 未安装"

        # 删除 .git 目录
        git_dir = skill_dir / ".git"
        if git_dir.exists():
            _rmtree_readonly(git_dir)

        # 方式1: 有 skill.json → 用结构化定义
        skill_json = skill_dir / "skill.json"
        if skill_json.exists():
            try:
                data = json.loads(skill_json.read_text(encoding="utf-8"))
                data.setdefault("id", repo_name)
                data.setdefault("icon", "⚡")
                data["source"] = "installed"
                data["github_url"] = url
                # 扫描知识库文件
                data["knowledge"] = self._scan_knowledge(skill_dir)
                skill_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                self._cache[data["id"]] = data
                return data, None
            except Exception as e:
                pass  # skill.json 解析失败，尝试方式2

        # 方式2: 没有 skill.json → 读 README 自动生成
        readme = self._find_readme(skill_dir)
        if not readme:
            _rmtree_readonly(skill_dir)
            return None, "仓库中找不到 skill.json 或 README"

        readme_content = self._read_text(readme)
        if not readme_content:
            _rmtree_readonly(skill_dir)
            return None, "无法读取 README 内容"

        # 从 README 提取信息
        name = self._extract_title(readme_content) or repo_name.replace("-", " ").replace("_", " ").title()
        description = self._extract_description(readme_content)
        knowledge = self._scan_knowledge(skill_dir)

        # 生成 system_prompt
        system_prompt = f"你正在使用一个来自 GitHub 的技能：{name}。\n\n"
        system_prompt += f"项目说明：{description}\n\n"
        if knowledge:
            system_prompt += "以下是该项目的关键文档内容，在回答相关问题时请参考：\n\n"
            for fname, content in knowledge.items():
                system_prompt += f"### {fname}\n{content[:2000]}\n\n"

        data = {
            "id": repo_name,
            "name": name,
            "icon": "📦",
            "description": description[:200],
            "system_prompt": system_prompt,
            "source": "installed",
            "github_url": url,
            "knowledge": knowledge,
        }

        # 写入 skill.json 以便后续加载
        (skill_dir / "skill.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._cache[data["id"]] = data
        return data, None

    def _find_readme(self, directory):
        """查找 README 文件"""
        for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
            p = directory / name
            if p.exists():
                return p
        return None

    def _read_text(self, path, max_len=5000):
        """安全读取文本文件"""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return text[:max_len]
        except Exception:
            return ""

    def _extract_title(self, content):
        """从 README 提取标题"""
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    def _extract_description(self, content):
        """从 README 提取描述（第一个非标题非空行）"""
        lines = content.split("\n")
        found_title = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                found_title = True
                continue
            if found_title and not line.startswith(("!", "-", "*", ">", "```", "|")):
                return line[:300]
        # 回退：取前200字符
        return content[:200].replace("\n", " ")

    def _scan_knowledge(self, skill_dir):
        """扫描仓库中的关键文档文件"""
        knowledge = {}
        # 优先读取的文件
        priority_files = [
            "README.md", "readme.md", "USAGE.md", "usage.md",
            "GUIDE.md", "guide.md", "DOCS.md", "docs.md",
            "INSTRUCTIONS.md", "instructions.md",
            "prompt.md", "system.md", "context.md",
        ]
        for fname in priority_files:
            p = skill_dir / fname
            if p.exists():
                content = self._read_text(p)
                if content:
                    knowledge[fname] = content

        # 扫描 docs/ 目录
        docs_dir = skill_dir / "docs"
        if docs_dir.exists():
            for f in docs_dir.glob("*.md"):
                if len(knowledge) < 10:  # 最多10个文件
                    content = self._read_text(f)
                    if content:
                        knowledge[f"docs/{f.name}"] = content

        return knowledge

    def delete_skill(self, skill_id):
        if skill_id not in self._cache:
            raise ValueError(f"技能 '{skill_id}' 不存在")
        if self._cache[skill_id].get("source") == "builtin":
            raise ValueError("不能删除内置技能")

        skill_dir = INSTALLED_DIR / skill_id
        if skill_dir.exists():
            _rmtree_readonly(skill_dir)
        del self._cache[skill_id]

    def reload(self):
        self._load_all()


skill_manager = SkillManager()
