# VerseNa 子代理验收测试

请使用当前项目的 `delegate_plan` 完成一次真实的子代理系统验收。这个任务只验证调度、依赖交接和结构化验收证据，不要修改 VerseNa 的真实源码，不要访问或修改 `backend/.env`、`backend/data/`、`data/`，也不要提交或推送 Git。

## 计划要求

请创建并执行以下 5 个节点，节点 ID、角色和依赖关系保持一致：

```text
inspect_code   explorer   depends_on=[]
inspect_tests  explorer   depends_on=[]
implement      executor   depends_on=[inspect_code, inspect_tests]
verify_tests   verifier   depends_on=[implement]
verify_types   verifier   depends_on=[implement]
```

`inspect_code` 和 `inspect_tests` 必须并行。`implement` 必须等待两个调查节点完成，并使用它们的 `dependency_context`，不要重复完整调查。`verify_tests` 和 `verify_types` 必须在 `implement` 完成后并行执行。

动态验收标准只能写在 `verify_tests` 和 `verify_types` 两个 verifier 节点上。不要把 `unit_tests`、`typecheck`、`lint`、`build` 或 `runtime_smoke` 之类的验收标准复制到 explorer、researcher 或 reviewer 节点；调查节点只负责定位和报告，不负责执行动态验收。

## 安全实现任务

`implement` 只允许在安全的临时目录或工作区内创建一个很小的测试文件，例如 `subagent_acceptance_marker.txt`，写入 `SUBAGENT_ACCEPTANCE_OK`，然后用 `file_manager` 回读确认。不要修改已有源码。

## 验收要求

在两个 verifier 开始前，先由 `inspect_tests` 只读发现当前 VerseNa 工具工作区中的真实项目目录。不要假设工具工作区就是 VerseNa 源码仓库根目录，也不要直接假设存在 `backend/tests`。优先寻找包含 `tests`、`package.json`、`tsconfig.json` 或后端测试入口的实际子目录，并把发现的相对目录写入交接报告。若确实没有可运行的后端测试或类型检查，必须保留缺失证据，不要为了让计划成功而创建或修改测试配置。

`verify_tests` 必须使用 `verification_exec` 在 `inspect_tests` 找到的实际目录执行真实后端测试。例如，只有当工作区内确实存在 `backend/tests` 时才使用：

```text
python -m pytest <实际测试目录> -q
```

检查 ID 使用 `unit_tests`。如果命令不可用、测试不存在、测试集为空或退出码非零，必须如实记录为 `missing_checks`、`needs_attention` 或失败，不能只根据自然语言报告声称通过。

`verify_types` 必须使用 `verification_exec` 在实际前端项目目录执行真实类型检查：

```text
npx tsc --noEmit
```

检查 ID 使用 `typecheck`，并在 verifier 节点的 `cwd` 中填写实际前端项目相对目录。不能用一次成功的 `npm test`、构建命令或静态阅读替代类型检查。若项目没有可用的 TypeScript 类型检查配置，必须如实记录 `missing_checks` 或 `needs_attention`。

## 最终报告

执行结束后，请打印结构化汇总，不要只写“测试通过”。至少包含：

1. 每个节点的 `id`、`role`、`status`、`depends_on`、开始和结束顺序。
2. `implement` 是否收到两个前序节点的 `dependency_context`，以及交接报告是否被实际利用。
3. 计划级 evidence 中的 `required_checks`、`passed_checks`、`missing_checks`、`unmatched_checks`。
4. 每个 verifier 的真实命令、退出码、工作目录、`verification_quality` 和测试数量。
5. 计划级 `verification_quality`、`failures`、`resolved_failures` 和最终状态。
6. 如果出现任何节点状态为 `needs_attention`、`needs_verification`、`error` 或 `skipped`，解释原因，不要把整个计划描述为完全成功。

完成后，主 Agent 还要独立复核关键 evidence，尤其确认两个 verifier 的检查都是真实执行过的，并确认计划级 `missing_checks` 为空后再给出最终结论。
