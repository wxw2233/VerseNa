import asyncio
import json

from agent.subagent import DEFAULT_TIMEOUT, READ_ONLY_ROLES, ROLES, subagent_manager
from agent.subagent_plan import subagent_plan_manager
from tools.base import BaseTool, ToolContext
from tools.results import tool_error


class DelegateTaskTool(BaseTool):
    name = "delegate_task"
    description = (
        "主动将一个边界明确的任务委派给独立子代理。"
        "explorer、researcher 和 reviewer 只读；executor 可串行修改文件、执行命令和验证结果。"
        "处理复杂任务时无需用户提醒，应主动判断是否可把调查、审查或明确的实现交给本工具。"
        "每次只委派一个任务，主代理等待结果后再继续。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": list(ROLES),
                "description": "explorer=代码探索，researcher=资料研究，reviewer=静态审查，verifier=运行受限命令做动态验收，executor=任务执行",
            },
            "task": {
                "type": "string",
                "description": "完整、独立、带明确交付要求的子任务",
            },
            "allowed_paths": {
                "type": "array",
                "maxItems": 20,
                "items": {"type": "string"},
                "description": "executor 允许修改的工作区相对路径；省略时仍受工作区边界限制",
            },
            "constraints": {
                "type": "array",
                "maxItems": 20,
                "items": {"type": "string"},
                "description": "必须遵守的任务约束和禁止事项",
            },
            "acceptance_criteria": {
                "type": "array",
                "maxItems": 20,
                "items": {"type": "string"},
                "description": "可验证的完成标准",
            },
            "timeout": {
                "type": "integer",
                "minimum": 10,
                "maximum": 300,
                "description": "超时秒数，默认 120",
            },
        },
        "required": ["role", "task"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        role: str,
        task: str,
        timeout: int = DEFAULT_TIMEOUT,
        allowed_paths: list[str] | None = None,
        constraints: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if not _context:
            return tool_error("MISSING_CONTEXT", "子代理执行上下文不可用")
        return await subagent_manager.run(
            role=role,
            task=task,
            context=_context,
            timeout=timeout,
            allowed_paths=allowed_paths,
            constraints=constraints,
            acceptance_criteria=acceptance_criteria,
        )


class DelegateTasksTool(BaseTool):
    name = "delegate_tasks"
    description = (
        "并行委派两个相互独立的只读调查任务给子代理。"
        "当复杂任务同时包含可独立进行的代码探索、资料研究或实现审查时应主动使用；"
        "两个子代理共享工作目录但上下文隔离，均不能修改文件或执行代码。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "description": "两个互不依赖、可以同时调查的子任务",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": sorted(READ_ONLY_ROLES),
                        },
                        "task": {
                            "type": "string",
                            "description": "完整、独立、带明确交付要求的子任务",
                        },
                        "constraints": {
                            "type": "array",
                            "maxItems": 20,
                            "items": {"type": "string"},
                        },
                        "acceptance_criteria": {
                            "type": "array",
                            "maxItems": 20,
                            "items": {"type": "string"},
                        },
                        "timeout": {
                            "type": "integer",
                            "minimum": 10,
                            "maximum": 300,
                        },
                    },
                    "required": ["role", "task"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["tasks"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        tasks: list,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if not _context:
            return tool_error("MISSING_CONTEXT", "子代理执行上下文不可用")
        if not isinstance(tasks, list) or len(tasks) != 2:
            return tool_error("INVALID_SUBAGENT_BATCH", "并行委派必须包含两个子任务")

        operations = []
        for spec in tasks:
            if not isinstance(spec, dict):
                return tool_error("INVALID_SUBAGENT_BATCH", "子任务格式无效")
            if str(spec.get("role") or "") not in READ_ONLY_ROLES:
                return tool_error("SUBAGENT_BATCH_READ_ONLY", "并行委派只允许只读子代理，executor 必须单独串行运行")
            optional = {}
            if spec.get("constraints"):
                optional["constraints"] = spec.get("constraints")
            if spec.get("acceptance_criteria"):
                optional["acceptance_criteria"] = spec.get("acceptance_criteria")
            operations.append(subagent_manager.run(
                role=str(spec.get("role") or ""),
                task=str(spec.get("task") or ""),
                timeout=spec.get("timeout", DEFAULT_TIMEOUT),
                context=_context,
                **optional,
            ))
        raw_results = await asyncio.gather(*operations)
        results = [json.loads(raw) for raw in raw_results]
        success = all(result.get("success") is True for result in results)
        return json.dumps({
            "type": "subagent_batch_result",
            "success": success,
            "message": "并行子代理调查完成" if success else "部分子代理未正常完成",
            "data": {"results": [result.get("data", result) for result in results]},
        }, ensure_ascii=False)


class DelegatePlanTool(BaseTool):
    name = "delegate_plan"
    description = (
        "执行一个包含 2 到 5 个节点的单层依赖任务计划。"
        "适用于有明确先后关系的探索、研究、审查和实现任务；"
        "无依赖的只读节点最多两个并行，executor 节点始终独占串行。"
        "不要用于简单任务，也不要创建递归或开放式任务树。"
    )
    node_properties = {
        "id": {
            "type": "string",
            "description": "计划内唯一短 ID，例如 inspect_backend",
        },
        "role": {
            "type": "string",
            "enum": list(ROLES),
            "description": "动态执行测试、类型检查、lint 或构建时必须使用 verifier；reviewer 主要用于静态审查",
        },
        "task": {
            "type": "string",
            "description": "边界明确、可以独立验收的子任务",
        },
        "depends_on": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string"},
            "description": "必须先成功完成的节点 ID；每个节点都必须填写，根节点使用空数组 []",
        },
        "allowed_paths": {
            "type": "array",
            "maxItems": 20,
            "items": {"type": "string"},
        },
        "constraints": {
            "type": "array",
            "maxItems": 20,
            "items": {"type": "string"},
        },
        "acceptance_criteria": {
            "type": "array",
            "maxItems": 20,
            "items": {"type": "string"},
        },
        "timeout": {
            "type": "integer",
            "minimum": 10,
            "maximum": 300,
        },
    }
    parameters = {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "minItems": 2,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": node_properties,
                    "required": ["id", "role", "task", "depends_on"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["nodes"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        nodes: list,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if not _context:
            return tool_error("MISSING_CONTEXT", "任务计划执行上下文不可用")
        return await subagent_plan_manager.run(nodes=nodes, context=_context)


def register(registry):
    registry.register(DelegateTaskTool())
    registry.register(DelegateTasksTool())
    registry.register(DelegatePlanTool())
