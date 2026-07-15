# 次元人格 — 消息展示改造设计（segments 结构）

> 日期：2026-07-15

## 1. 概述

改造 agent 消息返回方式，从逐 chunk 流式发送改为按段落（segment）发送。工具调用过程以时间线形式嵌入聊天气泡，用户可看到完整的工具调用链。

## 2. 消息数据结构

### 2.1 segment 结构

一条消息包含多个 segment：

```javascript
{
  role: 'assistant',
  segments: [
    { type: 'text', content: '我来帮你搜索一下。' },
    {
      type: 'tool',
      tool_name: 'web_search',
      tool_args: { query: 'Python教程' },
      status: 'running',  // running / done / error
      result_summary: '找到 5 条结果',
      result_detail: '...'  // 完整结果，可展开
    },
    { type: 'text', content: '根据搜索结果，...' }
  ],
  emoji: '😊',
  streaming: false
}
```

### 2.2 segment 类型

| 类型 | 字段 | 说明 |
|------|------|------|
| text | content | 文本内容，Markdown 渲染 |
| tool | tool_name, tool_args, status, result_summary, result_detail | 工具调用，渲染为时间线节点 |

### 2.3 tool status 状态机

```
running → done
running → error
```

---

## 3. 后端流式输出

### 3.1 react.py yield 格式

```python
# 文本段（流式追加，每个 chunk 是一个 text segment）
yield {"type": "segment", "segment": {"type": "text", "content": chunk.content}}

# 工具调用段（开始）
yield {"type": "segment", "segment": {
    "type": "tool",
    "tool_name": "web_search",
    "tool_args": {"query": "Python教程"},
    "status": "running"
}}

# 工具调用段（完成，更新同名 tool segment）
yield {"type": "segment", "segment": {
    "type": "tool",
    "tool_name": "web_search",
    "status": "done",
    "result_summary": "找到 5 条结果",
    "result_detail": "1. Python官方教程\n2. 廖雪峰..."
}}

# 工具调用段（错误）
yield {"type": "segment", "segment": {
    "type": "tool",
    "tool_name": "web_search",
    "status": "error",
    "result_summary": "搜索失败：网络超时"
}}
```

### 3.2 合并逻辑

连续的 text segment chunks 合并为一个 text segment：
- 第一个 chunk 创建新 text segment
- 后续 chunk 追加到当前 text segment 的 content

tool segment 按 tool_name 匹配更新：
- 收到 status=running → 新增 tool segment
- 收到 status=done/error → 更新同名 tool segment 的 status 和 result

---

## 4. 前端渲染

### 4.1 ChatBubble 改造

遍历 segments 渲染：

```vue
<div v-for="(seg, i) in msg.segments" :key="i">
  <!-- 文本段 -->
  <div v-if="seg.type === 'text'" class="text-seg" v-html="renderMarkdown(seg.content)" />

  <!-- 工具调用段时间线节点 -->
  <div v-if="seg.type === 'tool'" class="tool-seg">
    <div class="tool-header">
      <span class="tool-icon">{{ toolIcon(seg.tool_name) }}</span>
      <span class="tool-name">{{ seg.tool_name }}</span>
      <span class="tool-args">{{ summarizeArgs(seg.tool_args) }}</span>
      <span class="tool-status">
        <span v-if="seg.status === 'running'" class="spinner">⏳</span>
        <span v-if="seg.status === 'done'">✅</span>
        <span v-if="seg.status === 'error'">❌</span>
      </span>
    </div>
    <div class="tool-summary" v-if="seg.result_summary">{{ seg.result_summary }}</div>
    <div class="tool-detail" v-if="expandedTools[i]">
      <pre>{{ seg.result_detail }}</pre>
    </div>
    <button class="tool-expand" @click="toggleExpand(i)" v-if="seg.result_detail">
      {{ expandedTools[i] ? '收起' : '展开' }}
    </button>
  </div>
</div>
```

### 4.2 工具图标映射

| 工具 | 图标 |
|------|------|
| web_search | 🔍 |
| code_exec | 💻 |
| file_manager | 📁 |

### 4.3 CSS 样式

```css
.tool-seg {
  margin: 8px 0;
  padding: 8px 12px;
  background: rgba(124, 92, 252, 0.08);
  border-left: 3px solid var(--primary);
  border-radius: 0 8px 8px 0;
  font-size: 13px;
}
.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.tool-icon { font-size: 14px; }
.tool-name { font-weight: 600; color: var(--primary); }
.tool-args { color: var(--text-secondary); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-status { flex-shrink: 0; }
.tool-summary { margin-top: 4px; color: var(--text-secondary); font-size: 12px; }
.tool-detail { margin-top: 8px; padding: 8px; background: var(--bg-primary); border-radius: 4px; font-size: 12px; max-height: 200px; overflow-y: auto; }
.tool-expand { margin-top: 4px; background: none; border: none; color: var(--primary); cursor: pointer; font-size: 12px; }
.spinner { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
```

---

## 5. 前端 store 改造

### 5.1 chat.js

```javascript
// appendAgentChunk 改为 appendSegment
function appendSegment(segment) {
  const last = messages.value[messages.value.length - 1]
  if (!last || last.role !== 'assistant' || !last.streaming) {
    // 新建 assistant 消息
    messages.value.push({
      role: 'assistant',
      segments: [segment],
      streaming: true,
      emoji: null
    })
  } else {
    // 追加到现有消息
    if (segment.type === 'text') {
      // 合并连续 text segment
      const lastSeg = last.segments[last.segments.length - 1]
      if (lastSeg && lastSeg.type === 'text') {
        lastSeg.content += segment.content
      } else {
        last.segments.push(segment)
      }
    } else if (segment.type === 'tool') {
      // 查找同名 tool segment
      const existing = last.segments.find(s => s.type === 'tool' && s.tool_name === segment.tool_name && s.status === 'running')
      if (existing && segment.status !== 'running') {
        // 更新状态
        Object.assign(existing, segment)
      } else {
        last.segments.push(segment)
      }
    }
  }
}
```

---

## 6. 兼容性

- 旧消息（无 segments 字段）自动转换：`segments = [{ type: 'text', content: msg.content }]`
- 确认（confirm）和完成（done）消息格式不变
- 错误消息也改为 segment：`{ type: 'text', content: '[错误] ...' }`

---

## 7. 开发阶段

| 阶段 | 内容 |
|------|------|
| S0 | 后端 react.py 改为 segment yield 格式 |
| S1 | 前端 chat store 改为 appendSegment |
| S2 | 前端 ChatBubble 改为 segments 渲染 + 时间线样式 |
