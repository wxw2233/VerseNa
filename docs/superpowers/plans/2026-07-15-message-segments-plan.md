# 消息 segments 改造实现计划

**Goal:** 改造消息返回方式为 segments 结构，工具调用以时间线嵌入聊天气泡。

## S0: 后端 react.py 改造

### Task 1

**Files:**
- Modify: `backend/agent/react.py`

- [ ] 工具调用生成 tool_call_id（tc_{13位时间戳}_{3位序号}）
- [ ] text chunk yield 改为 segment 格式
- [ ] 工具调用 yield 改为 segment 格式（running → done/error）
- [ ] done 事件包含 emoji
- [ ] error 事件格式
- [ ] 测试 + 提交

## S1: 前端 store 改造

### Task 2

**Files:**
- Modify: `frontend/src/stores/chat.js`

- [ ] appendSegment（immutable 更新 + 状态优先级 + 组内排序）
- [ ] done 兜底（running→error + streaming=false + emoji）
- [ ] error 事件处理（running→error + 追加错误 text 段）
- [ ] 旧格式兼容（无 version/segments 自动转换）
- [ ] 构建 + 提交

## S2: 前端 ChatBubble 改造

### Task 3

**Files:**
- Modify: `frontend/src/components/ChatBubble.vue`

- [ ] 遍历 segments 渲染（text 段 + tool 段时间线节点）
- [ ] 工具图标映射（🔍/💻/📁）
- [ ] 状态配色（running 蓝脉冲、done 绿、error 红）
- [ ] 连续 tool 段纵向连接线（颜色跟随状态）
- [ ] 展开/折叠（expandedTools[tool_call_id]）
- [ ] 结果格式化（搜索→链接、代码→高亮、JSON→折叠）
- [ ] 长结果截断（200 行）
- [ ] 错误重试按钮（重新生成整条消息）
- [ ] 折叠全部/展开全部开关
- [ ] 构建 + 提交
