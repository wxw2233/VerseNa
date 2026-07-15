# 次元人格 — 消息展示改造设计（segments 结构 v3）

> 日期：2026-07-15

## 1. 概述

改造 agent 消息返回方式，从逐 chunk 流式发送改为按段落（segment）发送。工具调用过程以时间线形式嵌入聊天气泡，用户可看到完整的工具调用链。

## 2. 消息数据结构

### 2.1 消息根级

```javascript
{
  role: 'assistant',
  version: 2,
  segments: [...],
  expandedTools: { "tc_001": true, "tc_002": false },  // 展开状态，持久化到消息数据
  emoji: null,  // 流式过程中始终为 null，done 事件最终赋值
  streaming: true
}
```

### 2.2 segment 结构

```javascript
// 文本段
{ type: 'text', content: '我来帮你搜索一下。' }

// 工具段
{
  type: 'tool',
  tool_call_id: 'tc_001',  // 严格递增（时间戳+序号），前端按此排序
  tool_name: 'web_search',
  tool_args: { query: 'Python教程' },
  status: 'running',  // running → done / error
  result_summary: '找到 5 条结果',
  result_detail: '...'
}
```

### 2.3 匹配规则（单向状态机 + 全量匹配合并）

- 所有匹配使用 `tool_call_id`
- 状态只允许正向流转：`running → done / error`，不允许反向
- 收到 segment 时：
  - 按 tool_call_id 查找已有 tool segment
  - 若已存在：状态正向则更新，反向则忽略
  - 若不存在：新增（无论 status 是什么，解决乱序问题）

### 2.4 空片段过滤

content 为空字符串的 text segment 不新增、不追加。

---

## 3. 流式事件协议

| 事件 | 触发时机 | 格式 |
|------|---------|------|
| segment | 输出/更新一个消息片段 | `{"type": "segment", "segment": {...}}` |
| done | 流式正常结束 | `{"type": "done", "emoji": "😊"}` |
| error | 流式全局异常终止 | `{"type": "error", "message": "服务异常"}` |

**done 事件处理：**
1. 将当前 assistant 消息 streaming 置为 false
2. 所有残留 status=running 的 tool segment 兜底为 status=error + result_summary='执行超时或断流'
3. emoji 在 done 事件中最终赋值，流式过程中始终为 null

---

## 4. 后端流式输出

### 4.1 react.py yield 格式

```python
# 文本段
yield {"type": "segment", "segment": {"type": "text", "content": chunk.content}}

# 工具段（开始）
yield {"type": "segment", "segment": {
    "type": "tool",
    "tool_call_id": "tc_001",  # 严格递增
    "tool_name": "web_search",
    "tool_args": {"query": "Python教程"},
    "status": "running"
}}

# 工具段（完成）
yield {"type": "segment", "segment": {
    "type": "tool",
    "tool_call_id": "tc_001",
    "status": "done",
    "result_summary": "找到 5 条结果",
    "result_detail": "..."
}}

# done 事件
yield {"type": "done", "emoji": emoji_state.emoji}
```

### 4.2 Markdown 完整性约束

- 输出工具段前，必须闭合当前所有未闭合的 Markdown 语法（代码块、表格、列表、引用块）
- 禁止拆分复合语法结构

---

## 5. 前端 store

### 5.1 appendSegment（immutable 更新）

```javascript
function appendSegment(segment) {
  const messages = [...messagesRef.value]
  const last = messages[messages.length - 1]

  if (!last || last.role !== 'assistant' || !last.streaming) {
    messages.push({
      role: 'assistant', version: 2,
      segments: [{ ...segment }],
      expandedTools: {},
      streaming: true, emoji: null
    })
  } else {
    const segs = [...last.segments]
    if (segment.type === 'text') {
      if (!segment.content) return  // 空片段过滤
      const lastSeg = segs[segs.length - 1]
      if (lastSeg?.type === 'text') {
        segs[segs.length - 1] = { ...lastSeg, content: lastSeg.content + segment.content }
      } else {
        segs.push({ ...segment })
      }
    } else if (segment.type === 'tool') {
      const idx = segs.findIndex(s => s.type === 'tool' && s.tool_call_id === segment.tool_call_id)
      if (idx >= 0) {
        // 单向状态机：只允许正向流转
        const current = segs[idx]
        if (current.status === 'running' || segment.status === 'running') {
          segs[idx] = { ...current, ...segment }
        }
        // 已 done/error 且新也是 done/error → 忽略
      } else {
        segs.push({ ...segment })
      }
    }
    // tool_call_id 排序，确保并行工具展示顺序和调用顺序一致
    segs.sort((a, b) => {
      if (a.type !== 'tool' || b.type !== 'tool') return 0
      return (a.tool_call_id || '').localeCompare(b.tool_call_id || '')
    })
    messages[messages.length - 1] = { ...last, segments: segs }
  }
  messagesRef.value = messages
}
```

### 5.2 前端 Markdown 兜底

合并 text segment 时，检测未闭合的代码块标记（``` 数量为奇数），若下一个是 text 段则自动合并；若下一个是 tool 段，自动补全闭合标记。

### 5.3 流式结束

收到 done 事件时：
1. streaming 置为 false
2. emoji 赋值
3. 残留 running → error 兜底

---

## 6. 前端渲染

### 6.1 时间线

- 连续 tool segment 之间有左侧纵向连接线
- 连接线仅在连续相邻 tool 段之间，中间夹文本段时断开（符合"文本-工具-文本"叙事节奏）
- 不同状态配色：running（蓝色脉冲）、done（绿色）、error（红色）
- 展开状态用 expandedTools[tool_call_id]（持久化到消息数据）

### 6.2 结果按工具类型格式化

| 工具 | result_detail 格式 |
|------|-------------------|
| web_search | 标题 + 链接列表 |
| code_exec | 代码块 + 语法高亮 |
| file_manager | JSON 格式化 + 层级折叠 |
| 其他 | 纯文本 |

**长结果截断：** 超过 200 行默认截断，点击展开后全量渲染。

### 6.3 操作入口

- 错误状态显示「重试」按钮 = 重新生成整条消息（v2 范畴）
- 单工具精准重试作为 v3 规划
- 气泡顶部「折叠全部工具」总开关

### 6.4 容错

- 高版本降级：收到 version > 当前支持版本，降级为拼接所有 text segment 文本
- 未知类型容错：遇到未定义的 segment type，忽略或渲染为纯文本

### 6.5 CSS

```css
.tool-seg {
  margin: 8px 0;
  padding: 8px 12px;
  background: rgba(124, 92, 252, 0.08);
  border-left: 3px solid var(--primary);
  border-radius: 0 8px 8px 0;
  font-size: 13px;
  position: relative;
}
.tool-seg + .tool-seg::before {
  content: '';
  position: absolute;
  left: -3px; top: -8px;
  width: 3px; height: 8px;
  background: var(--primary);
}
.tool-seg[data-status="running"] { border-left-color: #3b82f6; }
.tool-seg[data-status="done"] { border-left-color: #22c55e; }
.tool-seg[data-status="error"] { border-left-color: #ef4444; }
.tool-header { display: flex; align-items: center; gap: 6px; }
.tool-name { font-weight: 600; color: var(--primary); }
.tool-args { color: var(--text-secondary); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-summary { margin-top: 4px; color: var(--text-secondary); font-size: 12px; }
.tool-detail { margin-top: 8px; padding: 8px; background: var(--bg-primary); border-radius: 4px; font-size: 12px; max-height: 200px; overflow-y: auto; }
.tool-actions { margin-top: 4px; display: flex; gap: 8px; }
.tool-expand, .tool-retry { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 12px; }
.spinner { animation: spin 1s linear infinite; display: inline-block; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
```

---

## 7. 开发阶段

| 阶段 | 内容 |
|------|------|
| S0 | 后端 react.py 改为 segment yield + tool_call_id + done 事件 |
| S1 | 前端 chat store 改为 appendSegment（immutable）+ 状态机 + 兜底 |
| S2 | 前端 ChatBubble 改为 segments 渲染 + 时间线 + 结果格式化 + 重试 |
| S3 | 测试：并发工具、乱序、长消息、流式结束兜底、高版本降级 |
