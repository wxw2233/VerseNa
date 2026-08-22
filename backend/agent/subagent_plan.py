import asyncio
import inspect
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from agent.subagent import (
    DEFAULT_TIMEOUT,
    MAX_TIMEOUT,
    READ_ONLY_ROLES,
    ROLES,
    subagent_manager,
)
from tools.results import tool_error, tool_result


MIN_PLAN_NODES = 2
MAX_PLAN_NODES = 5
MAX_DEPENDENCY_REPORT_CHARS = 8000
MIN_DEPENDENCY_REPORT_CHARS = 4000
MAX_DEPENDENCY_REPORT_CHARS = 200000
REPAIRABLE_PLAN_ERRORS = {
    "INVALID_SUBAGENT_PLAN",
    "INVALID_SUBAGENT_NODE_ID",
    "DUPLICATE_SUBAGENT_NODE",
    "INVALID_SUBAGENT_ROLE",
    "SUBAGENT_TASK_REQUIRED",
    "SUBAGENT_DEPENDENCY_REQUIRED",
    "INVALID_SUBAGENT_DEPENDENCY",
    "INVALID_SUBAGENT_TIMEOUT",
    "SUBAGENT_VERIFIER_ROLE_REQUIRED",
    "UNKNOWN_SUBAGENT_DEPENDENCY",
    "CYCLIC_SUBAGENT_PLAN",
    "AMBIGUOUS_SUBAGENT_DEPENDENCIES",
}
DYNAMIC_VERIFICATION_PATTERN = re.compile(
    r"(?:运行|执行|跑|run|execute).{0,24}"
    r"(?:测试|类型检查|构建|lint|test|build|tsc|pytest|unittest|vitest|jest|eslint|npm|pnpm|yarn|cargo|mypy|ruff)",
    re.IGNORECASE,
)


class SubagentPlanManager:
    async def run(self, *, nodes: list[dict[str, Any]], context) -> str:
        validated = self._validate(nodes)
        if isinstance(validated, str):
            return self._with_repair_guidance(validated, nodes)

        plan_id = f"plan_{uuid.uuid4().hex}"
        started = time.monotonic()
        node_map = {node["id"]: node for node in validated}
        states = {
            node["id"]: {
                "id": node["id"],
                "role": node["role"],
                "task": node["task"],
                "depends_on": node["depends_on"],
                "status": "pending",
                "report": "",
            }
            for node in validated
        }
        await self._emit(context, plan_id, "running", states, "正在安排子任务")

        while any(state["status"] == "pending" for state in states.values()):
            if context.stop_event and context.stop_event.is_set():
                for state in states.values():
                    if state["status"] == "pending":
                        state["status"] = "stopped"
                        state["report"] = "主任务已停止。"
                break

            changed = self._skip_blocked(states)
            ready = [
                node_map[node_id]
                for node_id, state in states.items()
                if state["status"] == "pending"
                and all(states[dep]["status"] == "done" for dep in state["depends_on"])
            ]
            if not ready:
                if changed:
                    continue
                return tool_error("SUBAGENT_PLAN_STALLED", "任务计划无法继续调度")

            ready_readonly = [
                node for node in ready if node["role"] in READ_ONLY_ROLES
            ][:2]
            if ready_readonly:
                batch = ready_readonly
            else:
                executor = next((node for node in ready if node["role"] == "executor"), None)
                batch = [executor] if executor else []
            if not batch:
                return tool_error("SUBAGENT_PLAN_STALLED", "任务计划中没有可调度的节点")
            for node in batch:
                states[node["id"]]["status"] = "running"
            await self._emit(
                context,
                plan_id,
                "running",
                states,
                "正在执行: " + "、".join(node["id"] for node in batch),
            )

            raw_results = await asyncio.gather(*[
                self._run_node(plan_id, node, states, context)
                for node in batch
            ])
            for node, raw in zip(batch, raw_results):
                result = json.loads(raw)
                data = result.get("data") or {}
                state = states[node["id"]]
                state["status"] = data.get("status") or ("done" if result.get("success") else "error")
                state["report"] = str(data.get("report") or result.get("message") or "")
                state["evidence"] = data.get("evidence") or {}
                state["subagent_id"] = data.get("run_id") or ""
                state["duration_ms"] = data.get("duration_ms") or 0
                state["budget"] = data.get("budget") or {}
                if node["role"] == "executor" and state["status"] == "done":
                    self._audit_executor_result(state, context)

            await self._emit(context, plan_id, "running", states, "正在更新任务计划")

        success = all(state["status"] == "done" for state in states.values())
        final_status = "done" if success else "partial"
        duration_ms = int((time.monotonic() - started) * 1000)
        evidence = self._aggregate_evidence(states)
        await self._emit(
            context,
            plan_id,
            final_status,
            states,
            "任务计划完成" if success else "任务计划部分完成",
            duration_ms=duration_ms,
            evidence=evidence,
        )
        return tool_result(
            success,
            error="" if success else "SUBAGENT_PLAN_PARTIAL",
            message="任务计划完成" if success else "任务计划存在失败、停止或跳过的节点",
            data={
                "plan_id": plan_id,
                "status": final_status,
                "nodes": list(states.values()),
                "duration_ms": duration_ms,
                "evidence": evidence,
            },
            result_type="subagent_plan_result",
        )

    async def _run_node(self, plan_id, node, states, context) -> str:
        report_limit = self._dependency_report_limit(context)
        dependency_context = []
        for dependency in node["depends_on"]:
            state = states[dependency]
            dependency_context.append({
                "id": dependency,
                "role": state.get("role") or "",
                "report": str(state.get("report") or "")[:report_limit],
                "evidence": state.get("evidence") or {},
            })
        return await subagent_manager.run(
            role=node["role"],
            task=node["task"],
            context=context,
            timeout=node["timeout"],
            allowed_paths=node["allowed_paths"],
            constraints=node["constraints"],
            acceptance_criteria=node["acceptance_criteria"],
            plan_id=plan_id,
            node_id=node["id"],
            depends_on=node["depends_on"],
            dependency_context=dependency_context,
        )

    @staticmethod
    def _dependency_report_limit(context) -> int:
        """Use the same configurable handoff budget as direct delegation.

        The plan layer used to clip every dependency at 8K characters even
        after the user increased the subagent report budget. That discarded
        the most useful portion of investigations before the executor saw it.
        """
        config = getattr(context, "agent_config", None) or {}
        try:
            configured = int(config.get("subagent_report_max_chars", MAX_DEPENDENCY_REPORT_CHARS))
        except (TypeError, ValueError):
            configured = MAX_DEPENDENCY_REPORT_CHARS
        return max(MIN_DEPENDENCY_REPORT_CHARS, min(configured, MAX_DEPENDENCY_REPORT_CHARS))

    @staticmethod
    def _skip_blocked(states: dict[str, dict[str, Any]]) -> bool:
        changed = False
        terminal_failures = {"error", "stopped", "skipped", "needs_verification", "needs_attention"}
        for state in states.values():
            if state["status"] != "pending":
                continue
            failed = [dep for dep in state["depends_on"] if states[dep]["status"] in terminal_failures]
            if failed:
                state["status"] = "skipped"
                state["report"] = f"前序任务未成功完成: {', '.join(failed)}"
                changed = True
        return changed

    @staticmethod
    def _aggregate_evidence(states):
        modified = set()
        verifications = []
        failures = []
        resolved_failures = []
        verification_quality = []
        required_checks = []
        passed_checks = []
        missing_checks = []
        unmatched_checks = []
        for state in states.values():
            evidence = state.get("evidence") or {}
            modified.update(evidence.get("modified_files") or [])
            verifications.extend(evidence.get("verifications") or [])
            failures.extend(evidence.get("failures") or [])
            resolved_failures.extend(evidence.get("resolved_failures") or [])
            verification_quality.extend(evidence.get("verification_quality") or [])
            required_checks.extend(evidence.get("required_checks") or [])
            passed_checks.extend(evidence.get("passed_checks") or [])
            missing_checks.extend(evidence.get("missing_checks") or [])
            unmatched_checks.extend(evidence.get("unmatched_checks") or [])
            if state["status"] not in {"done", "pending", "running"}:
                failures.append(f"{state['id']}: {state['status']}")
        required_checks = list(dict.fromkeys(required_checks))
        passed_checks = list(dict.fromkeys(passed_checks))
        return {
            "modified_files": sorted(modified),
            "verifications": verifications[-20:],
            "failures": failures[-20:],
            "resolved_failures": resolved_failures[-20:],
            "verification_quality": verification_quality[-20:],
            "required_checks": required_checks,
            "passed_checks": passed_checks,
            "missing_checks": [
                check for check in required_checks if check not in passed_checks
            ],
            "unmatched_checks": list(dict.fromkeys(unmatched_checks)),
        }

    @staticmethod
    def _audit_executor_result(state: dict[str, Any], context) -> None:
        """Downgrade executor claims that do not match the current worktree.

        The executor's narrative remains useful reference data, but the plan
        cannot treat a reported change as completed until its declared paths
        still exist beneath the shared workspace.  This guards against stale
        reports, path mistakes and concurrent worktree changes without
        attempting to infer file contents from natural-language prose.
        """
        evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
        parent_audit = evidence.get("parent_audit") if isinstance(evidence.get("parent_audit"), dict) else {}
        if parent_audit.get("status") == "mismatch":
            state["status"] = "needs_attention"
            return
        # SubagentManager already compares the executor's before/after workspace
        # snapshots.  Do not overwrite that richer audit with a paths-exist
        # check when it is available.
        if parent_audit.get("status") in {"verified", "no_changes"}:
            return
        reported_paths = [str(path).strip() for path in evidence.get("modified_files") or [] if str(path).strip()]
        if not reported_paths:
            return
        try:
            workspace = Path(context.workspace).resolve()
        except (OSError, TypeError, ValueError):
            return
        missing = []
        outside = []
        for raw_path in reported_paths:
            try:
                candidate = Path(raw_path)
                if not candidate.is_absolute():
                    candidate = workspace / candidate
                candidate = candidate.resolve()
            except (OSError, TypeError, ValueError):
                missing.append(raw_path)
                continue
            if not candidate.is_relative_to(workspace):
                outside.append(raw_path)
            elif not candidate.exists():
                missing.append(raw_path)
        if not missing and not outside:
            evidence["parent_audit"] = {
                "status": "paths_present",
                "checked_files": reported_paths[:20],
            }
            return
        details = []
        if missing:
            details.append("报告的改动文件不存在: " + ", ".join(missing[:8]))
        if outside:
            details.append("报告的改动路径超出工作区: " + ", ".join(outside[:8]))
        message = "；".join(details)
        evidence.setdefault("failures", []).append("父代理二次核验: " + message)
        evidence["parent_audit"] = {
            "status": "mismatch",
            "message": message,
            "checked_files": reported_paths[:20],
        }
        state["status"] = "needs_attention"
        state["report"] = (str(state.get("report") or "") + "\n\n父代理二次核验失败: " + message).strip()

    @staticmethod
    def _with_repair_guidance(result: str, nodes) -> str:
        try:
            payload = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result
        error = str(payload.get("error") or "")
        if error not in REPAIRABLE_PLAN_ERRORS:
            return result

        node_summaries = []
        if isinstance(nodes, list):
            for raw in nodes[:MAX_PLAN_NODES]:
                if not isinstance(raw, dict):
                    continue
                node_summaries.append({
                    "id": str(raw.get("id") or "")[:40],
                    "role": str(raw.get("role") or "")[:40],
                    "depends_on": raw.get("depends_on") if isinstance(raw.get("depends_on"), list) else None,
                })
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        data["repair"] = {
            "retryable": True,
            "max_retries": 1,
            "failed_error": error,
            "failed_nodes": node_summaries,
            "requirements": [
                "重新提交完整的 delegate_plan，不要只提交局部节点",
                "每个节点必须显式填写 depends_on，根节点使用 []",
                "实现节点依赖其前序调查；动态命令验收使用 verifier 并依赖被验收的实现",
                "所有依赖 ID 必须存在且图中不能有环",
                "保留原任务目标、允许路径、约束和验收标准",
            ],
        }
        payload["data"] = data
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def _validate(cls, nodes):
        if not isinstance(nodes, list) or not MIN_PLAN_NODES <= len(nodes) <= MAX_PLAN_NODES:
            return tool_error(
                "INVALID_SUBAGENT_PLAN",
                f"任务计划必须包含 {MIN_PLAN_NODES} 到 {MAX_PLAN_NODES} 个节点",
            )
        normalized = []
        ids = set()
        for raw in nodes:
            if not isinstance(raw, dict):
                return tool_error("INVALID_SUBAGENT_PLAN", "任务节点格式无效")
            node_id = str(raw.get("id") or "").strip()
            role = str(raw.get("role") or "").strip()
            task = str(raw.get("task") or "").strip()
            if not node_id or len(node_id) > 40 or not node_id.replace("_", "").replace("-", "").isalnum():
                return tool_error("INVALID_SUBAGENT_NODE_ID", f"无效任务节点 ID: {node_id}")
            if node_id in ids:
                return tool_error("DUPLICATE_SUBAGENT_NODE", f"任务节点 ID 重复: {node_id}")
            if role not in ROLES:
                return tool_error("INVALID_SUBAGENT_ROLE", f"不支持的子代理角色: {role}")
            if not task:
                return tool_error("SUBAGENT_TASK_REQUIRED", f"任务节点 {node_id} 缺少任务描述")
            if "depends_on" not in raw:
                return tool_error(
                    "SUBAGENT_DEPENDENCY_REQUIRED",
                    f"节点 {node_id} 必须显式填写 depends_on；根节点请填写空数组 []",
                )
            dependencies = raw.get("depends_on") or []
            if not isinstance(dependencies, list) or len(dependencies) > MAX_PLAN_NODES - 1:
                return tool_error("INVALID_SUBAGENT_DEPENDENCY", f"节点 {node_id} 的依赖必须是数组")
            dependencies = [str(dep).strip() for dep in dependencies]
            if any(not dep for dep in dependencies) or len(set(dependencies)) != len(dependencies):
                return tool_error("INVALID_SUBAGENT_DEPENDENCY", f"节点 {node_id} 包含空白或重复依赖")
            try:
                timeout = max(10, min(int(raw.get("timeout") or DEFAULT_TIMEOUT), MAX_TIMEOUT))
            except (TypeError, ValueError):
                return tool_error("INVALID_SUBAGENT_TIMEOUT", f"节点 {node_id} 的超时参数无效")
            ids.add(node_id)
            normalized.append({
                "id": node_id,
                "role": role,
                "task": task[:8000],
                "depends_on": dependencies,
                "timeout": timeout,
                "allowed_paths": raw.get("allowed_paths") or [],
                "constraints": raw.get("constraints") or [],
                "acceptance_criteria": raw.get("acceptance_criteria") or [],
            })

        for node in normalized:
            verification_text = "\n".join([
                node["task"],
                *[str(value) for value in node["acceptance_criteria"]],
            ])
            if node["role"] == "reviewer" and DYNAMIC_VERIFICATION_PATTERN.search(verification_text):
                return tool_error(
                    "SUBAGENT_VERIFIER_ROLE_REQUIRED",
                    f"节点 {node['id']} 要求实际运行验证命令，角色必须使用 verifier；reviewer 仅用于静态审查",
                )

        for node in normalized:
            unknown = [dep for dep in node["depends_on"] if dep not in ids]
            if unknown:
                return tool_error("UNKNOWN_SUBAGENT_DEPENDENCY", f"节点 {node['id']} 依赖不存在: {', '.join(unknown)}")
            if node["id"] in node["depends_on"]:
                return tool_error("CYCLIC_SUBAGENT_PLAN", f"节点 {node['id']} 不能依赖自身")

        root_readonly = {
            node["id"]
            for node in normalized
            if not node["depends_on"] and node["role"] in READ_ONLY_ROLES
        }
        root_executors = [
            node["id"]
            for node in normalized
            if not node["depends_on"] and node["role"] == "executor"
        ]
        if root_readonly and root_executors:
            return tool_error(
                "AMBIGUOUS_SUBAGENT_DEPENDENCIES",
                "executor 与只读节点不能同时作为根节点；请显式声明调查、实现和验证之间的 depends_on",
                data={
                    "root_executors": root_executors,
                    "root_readonly": sorted(root_readonly),
                },
            )

        visiting = set()
        visited = set()
        graph = {node["id"]: node["depends_on"] for node in normalized}

        def visit(node_id):
            if node_id in visiting:
                return False
            if node_id in visited:
                return True
            visiting.add(node_id)
            if not all(visit(dep) for dep in graph[node_id]):
                return False
            visiting.remove(node_id)
            visited.add(node_id)
            return True

        if not all(visit(node_id) for node_id in graph):
            return tool_error("CYCLIC_SUBAGENT_PLAN", "任务计划存在循环依赖")
        return normalized

    @staticmethod
    async def _emit(context, plan_id, status, states, detail, **extra):
        callback = context.progress_callback
        if not callback:
            return
        segment = {
            "type": "subagent_plan",
            "plan_id": plan_id,
            "status": status,
            "detail": detail,
            "nodes": [dict(state) for state in states.values()],
            **extra,
        }
        try:
            result = callback({"type": "segment", "segment": segment})
            if inspect.isawaitable(result):
                await result
        except Exception:
            pass


subagent_plan_manager = SubagentPlanManager()
