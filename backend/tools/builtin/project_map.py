import json

from agent.project_map import architecture_summary, build_project_map, search_project_map
from tools.base import BaseTool, ToolContext
from tools.paths import resolve_tool_path, ToolPathError
from tools.results import tool_error, tool_result


class ProjectMapTool(BaseTool):
    name = "project_map"
    description = (
        "理解当前工作区的项目架构。可查看入口、核心模块、符号和脚本，"
        "或按关键词查询模块依赖；需要重新扫描时使用 refresh。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["summary", "inspect", "search", "refresh"],
                "description": "summary 查看摘要，inspect 查看详细索引，search 查询模块，refresh 重新扫描",
            },
            "query": {"type": "string", "description": "搜索路径、符号名、导入模块或文档内容"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "offset": {"type": "integer", "minimum": 0, "maximum": 100000},
            "include": {
                "type": "array",
                "items": {"type": "string", "enum": ["modules", "tree", "facts", "docs", "scripts"]},
                "description": "inspect 可选返回部分；默认返回 modules、facts、docs 和 scripts 的有限摘要",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        action: str = "summary",
        query: str = "",
        limit: int = 20,
        offset: int = 0,
        include: list[str] | None = None,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if not _context:
            return tool_error("MISSING_CONTEXT", "工具执行上下文不可用")
        if action not in {"summary", "inspect", "search", "refresh"}:
            return tool_error("INVALID_ACTION", "action 必须是 summary、inspect、search 或 refresh")
        try:
            workspace = resolve_tool_path(_context, ".").check_path
            data = build_project_map(workspace, refresh=action == "refresh")
            metadata = {
                "index_version": data.get("index_version", data.get("version")),
                "workspace": data.get("workspace"),
                "generated_at": data.get("generated_at"),
                "source_revision": data.get("source_revision"),
                "source_revision_files": data.get("source_revision_files", 0),
                "source_revision_truncated": data.get("source_revision_truncated", False),
                "truncated": data.get("truncated", False),
            }
            if action == "summary":
                return tool_result(True, message="项目架构摘要已生成", data={
                    **metadata,
                    "summary": architecture_summary(workspace),
                })
            if action == "search":
                return tool_result(True, message="项目架构搜索完成", data={
                    **metadata,
                    "query": query,
                    "results": search_project_map(workspace, query, limit),
                })
            if action == "inspect":
                try:
                    limit = max(1, min(int(limit), 50))
                    offset = max(0, min(int(offset), len(data.get("modules") or [])))
                except (TypeError, ValueError):
                    return tool_error("INVALID_PAGING", "limit 和 offset 必须是整数")
                requested = set(include or {"modules", "facts", "docs", "scripts"})
                modules = data.get("modules") or []
                view = {
                    **metadata,
                    "file_count": data.get("file_count", 0),
                    "scanned_paths_total": len(data.get("scanned_paths") or []),
                    "ignored_paths": data.get("ignored_paths", []),
                    "module_offset": offset,
                    "module_limit": limit,
                    "module_total": len(modules),
                    "module_next_offset": offset + limit if offset + limit < len(modules) else None,
                }
                if "modules" in requested:
                    view["modules"] = modules[offset:offset + limit]
                if "tree" in requested:
                    view["top_level"] = data.get("top_level", [])[:120]
                    view["entrypoints"] = data.get("entrypoints", [])[:40]
                    view["scanned_paths"] = (data.get("scanned_paths") or [])[:120]
                if "facts" in requested:
                    view["project_types"] = data.get("project_types", [])
                    view["framework_facts"] = data.get("framework_facts", {})
                if "docs" in requested:
                    view["architecture_docs"] = data.get("architecture_docs", {})
                if "scripts" in requested:
                    view["scripts"] = data.get("scripts", {})
                    view["script_sources"] = data.get("script_sources", [])
                    view["primary_script_source"] = data.get("primary_script_source")
                return tool_result(True, message="项目架构索引已读取", data=view)
            return tool_result(True, message="项目架构索引已刷新", data={
                **metadata,
                "summary": architecture_summary(workspace),
            })
        except (ToolPathError, OSError, ValueError) as exc:
            return tool_error("PROJECT_MAP_FAILED", str(exc))


def register(registry):
    registry.register(ProjectMapTool())
