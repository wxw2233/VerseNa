# 次元人格 — 消息展示改造设计（segments 结构 v2）

> 日期：2026-07-15

## 1. 概述

改造 agent 消息返回方式，从逐 chunk 流式发送改为按段落（segment）发送。工具调用过程以时间线形式嵌入聊天气泡，用户可看到完整的工具调用链。

## 2. 消息数据结构

### 2.1 消息根级

```javascript
{
  role: 'assistant',
  version: 2,  // 消息格式版本号，便于后续兼容
  segments: [...],
  emoji: '😊',
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
  tool_call_id: 'tc_001',  // 唯一标识，UUID 或递增 ID
  tool_name: 'web_search',
  tool_args: { query: 'Python教程' },
  status: 'running',  // running / done / error
  result_summary: '找到 5 条结果',
  result_detail: '...'
}
```

### 2.3 匹配规则

**所有工具段匹配使用 `tool_call_id`**，不使用 tool_name。后端每次工具调用生成唯一 tool_call_id，前端按此 ID 匹配更新。

---

## 3. 后端流式输出

### 3.1 react.py yield 格式

```python
# 文本段
yield {"type": "segment", "segment": {"type": "text", "content": chunk.content}}

# 工具段（开始）
yield {"type": "segment", "segment": {
    "type": "tool",
    "tool_call_id": "tc_001",
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
    "result_detail": "1. Python官方教程\n2. 廖雪峰..."
}}
```

### 3.2 合并逻辑

- 连续 text segment chunks 合并为一个 text segment
- 工具段按 tool_call_id 匹配更新，不按 tool_name

### 3.3 工具调用时机

尽量在 Markdown 语义边界（段落结束、列表完结）处触发工具调用，避免拆分代码块、表格等复合结构。

---

## 4. 前端 store

### 4.1 appendSegment（immutable 更新）

```javascript
function appendSegment(segment) {
  const messages = [...messagesRef.value]
  const last = messages[messages.length - 1]

  if (!last || last.role !== 'assistant' || !last.streaming) {
    messages.push({
      role: 'assistant', version: 2,
      segments: [{ ...segment }],
      streaming: true, emoji: null
    })
  } else {
    const segs = [...last.segments]
    if (segment.type === 'text') {
      const lastSeg = segs[segs.length - 1]
      if (lastSeg?.type === 'text') {
        segs[segs.length - 1] = { ...lastSeg, content: lastSeg.content + segment.content }
      } else {
        segs.push({ ...segment })
      }
    } else if (segment.type === 'tool') {
      const idx = segs.findIndex(s => s.type === 'tool' && s.tool_call_id === segment.tool_call_id)
      if (idx >= 0 && segment.status !== 'running') {
        segs[idx] = { ...segs[idx], ...segment }
      } else {
        segs.push({ ...segment })
      }
    }
    messages[messages.length - 1] = { ...last, segments: segs }
  }
  messagesRef.value = messages
}
```

### 4.2 流式结束

收到 done 事件时：
1. `streaming` 置为 false
2. 所有残留 status=running 的 tool segment 兜底为 status=error + result_summary='执行超时或断流'

---

## 5. 前端渲染

### 5.1 ChatBubble 时间线

```
┌─────────────────────────────────────────┐
│  🤖 Agent 消息                          │
│                                         │
│  我来帮你搜索一下。                       │
│                                         │
│  │ ┌─ 🔍 web_search ───────────────┐   │
│  │ │  搜索「Python教程」               │   │
│  │ │  ✅ 找到 5 条结果          [展开] │   │
│  │ └────────────────────────────────┘   │
│  │                                      │
│  │ ┌─ 💻 code_exec ────────────────┐   │
│  │ │  python -c "print('hello')"     │   │
│  │ │  ✅ hello                [展开] │   │
│  │ └────────────────────────────────┘   │
│                                         │
│  根据搜索结果，Python 教程推荐...        │
│                                    😊   │
└─────────────────────────────────────────┘
```

- 连续 tool segment 之间有左侧纵向连接线
- 不同状态不同配色：running（蓝色脉冲）、done（绿色）、error（红色）
- 展开状态用 tool_call_id 作为 key（不用数组索引）

### 5.2 结果按工具类型格式化

| 工具 | result_detail 格式 |
|------|-------------------|
| web_search | 标题 + 链接列表 |
| code_exec | 代码块 + 语法高亮 |
| file_manager | JSON 格式化 + 层级折叠 |
| 其他 | 纯文本 |

### 5.3 操作入口

- 错误状态的 tool segment 显示「重试」按钮
- 气泡顶部显示「折叠全部工具」总开关

### 5.4 CSS

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
/* 纵向连接线 */
.tool-seg + .tool-seg::before {
  content: '';
  position: absolute;
  left: -3px;
  top: -8px;
  width: 3px;
  height: 8px;
  background: var(--primary);
}
/* 状态配色 */
.tool-seg[data-status="running"] { border-left-color: #3b82f6; }
.tool-seg[data-status="done"] { border-left-color: #22c55e; }
.tool-seg[data-status="error"] { border-left-color: #ef4444; }
.tool-header { display: flex; align-items: center; gap: 6px; }
.tool-icon { font-size: 14px; }
.tool-name { font-weight: 600; color: var(--primary); }
.tool-args { color: var(--text-secondary); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-status { flex-shrink: 0; }
.tool-summary { margin-top: 4px; color: var(--text-secondary); font-size: 12px; }
.tool-detail { margin-top: 8px; padding: 8px; background: var(--bg-primary); border-radius: 4px; font-size: 12px; max-height: 200px; overflow-y: auto; }
.tool-actions { margin-top: 4px; display: flex; gap: 8px; }
.tool-expand, .tool-retry { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 12px; }
.spinner { animation: spin 1s linear infinite; display: inline-block; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
```

---

## 6. 兼容性

- 旧消息（无 version 字段）自动转换：`segments = [{ type: 'text', content: msg.content }]`
- 确认（confirm）和完成（done）消息格式不变
- 错误消息也改为 segment

---

## 7. 开发阶段

| 阶段 | 内容 |
|------|------|
| S0 | 后端 react.py 改为 segment yield + tool_call_id |
| S1 | 前端 chat store 改为 appendSegment（immutable）+ done 兜底 |
| S2 | 前端 ChatBubble 改为 segments 渲染 + 时间线 + 结果格式化 + 重试按钮 |
| S3 | 测试：并发工具、乱序返回、长消息渲染、流式结束兜底 |
