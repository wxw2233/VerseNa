# 次元人格 — 消息展示改造设计（segments 结构 v4）

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
  expandedTools: { "tc_001": true },  // 展开状态持久化，默认折叠
  emoji: null,  // 流式过程中始终为 null，done 事件最终赋值
  streaming: true
}
```

### 2.2 segment 结构

```javascript
{ type: 'text', content: '我来帮你搜索一下。' }

{
  type: 'tool',
  tool_call_id: 'tc_1721023456789_001',  // tc_{13位时间戳}_{3位序号}
  tool_name: 'web_search',
  tool_args: { query: 'Python教程' },
  status: 'running',
  result_summary: '找到 5 条结果',
  result_detail: '...'
}
```

### 2.3 tool_call_id 格式

`tc_{13位毫秒时间戳}_{3位序号}`，如 `tc_1721023456789_001`。保证同一条消息内严格单调递增，前端 localeCompare 排序与调用顺序一致。

### 2.4 匹配规则（状态优先级）

```javascript
const statusPriority = { running: 1, done: 2, error: 3 }
```

- 按 tool_call_id 查找已有 tool segment
- 若已存在：仅当新状态优先级 > 当前状态优先级时更新
- 若不存在：新增

### 2.5 空片段过滤

content 为空字符串的 text segment 不新增、不追加。

---

## 3. 流式事件协议

| 事件 | 触发时机 | 格式 |
|------|---------|------|
| segment | 输出/更新一个消息片段 | `{"type": "segment", "segment": {...}}` |
| done | 流式正常结束 | `{"type": "done", "emoji": "😊"}` |
| error | 流式全局异常终止 | `{"type": "error", "message": "服务异常"}` |

---

## 4. 后端流式输出

### 4.1 yield 格式

```python
yield {"type": "segment", "segment": {"type": "text", "content": chunk.content}}

yield {"type": "segment", "segment": {
    "type": "tool",
    "tool_call_id": f"tc_{int(time.time()*1000):013d}_{seq:03d}",
    "tool_name": "web_search",
    "tool_args": {"query": "Python教程"},
    "status": "running"
}}

yield {"type": "segment", "segment": {
    "type": "tool", "tool_call_id": "tc_...", "status": "done",
    "result_summary": "找到 5 条结果", "result_detail": "..."
}}

yield {"type": "done", "emoji": emoji_state.emoji}
```

### 4.2 Markdown 完整性约束

输出工具段前，必须闭合所有未闭合的 Markdown 复合结构（代码块、表格、列表、引用块）。

### 4.3 持久化约束

消息持久化到数据库时，必须以 done/error 事件后的最终状态为准，禁止保存流式中间状态。

---

## 5. 前端 store

### 5.1 appendSegment（immutable + 状态优先级）

```javascript
const statusPriority = { running: 1, done: 2, error: 3 }

function appendSegment(segment) {
  const messages = [...messagesRef.value]
  const last = messages[messages.length - 1]

  if (!last || last.role !== 'assistant' || !last.streaming) {
    messages.push({
      role: 'assistant', version: 2,
      segments: segment.content ? [{ ...segment }] : [],
      expandedTools: {}, streaming: true, emoji: null
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
        if (statusPriority[segment.status] > statusPriority[segs[idx].status]) {
          segs[idx] = { ...segs[idx], ...segment }
        }
      } else {
        segs.push({ ...segment })
      }
    }

    // 连续 tool 分组组内排序（text 段位置不动）
    const sorted = []
    let toolGroup = []
    for (const seg of segs) {
      if (seg.type === 'tool') {
        toolGroup.push(seg)
      } else {
        if (toolGroup.length) {
          toolGroup.sort((a, b) => (a.tool_call_id || '').localeCompare(b.tool_call_id || ''))
          sorted.push(...toolGroup)
          toolGroup = []
        }
        sorted.push(seg)
      }
    }
    if (toolGroup.length) {
      toolGroup.sort((a, b) => (a.tool_call_id || '').localeCompare(b.tool_call_id || ''))
      sorted.push(...toolGroup)
    }

    messages[messages.length - 1] = { ...last, segments: sorted }
  }
  messagesRef.value = messages
}
```

### 5.2 流式结束（done）

1. streaming 置为 false
2. emoji 赋值
3. 残留 running → error 兜底（result_summary='执行超时或断流'）

### 5.3 全局 error 事件处理

收到 error 事件时：
1. streaming 置为 false
2. 残留 running → error（result_summary='服务异常，执行中断'）
3. 追加 text 段：`{ type: 'text', content: '⚠️ ' + error.message }`

### 5.4 旧格式兼容

消息无 version 且无 segments 时，自动转换：
```javascript
{
  role: msg.role, version: 1,
  segments: [{ type: 'text', content: msg.content || '' }],
  expandedTools: {}, emoji: msg.emoji || null, streaming: false
}
```

### 5.5 前端 Markdown 兜底

仅做代码块闭合检测（``` 数量为奇数时自动补全），其余结构依赖后端保证。

---

## 6. 前端渲染

### 6.1 时间线

- 连续 tool 段之间有左侧纵向连接线
- 连接线颜色跟随相邻工具段状态（running 蓝、done 绿、error 红）
- 连接线仅在连续相邻 tool 段之间，中间夹 text 段时断开
- expandedTools 默认全部折叠，用户手动展开的状态持久化
- 「折叠全部」= 清空 expandedTools

### 6.2 结果格式化

| 工具 | result_detail |
|------|--------------|
| web_search | 标题 + 链接列表 |
| code_exec | 代码块 + 语法高亮 |
| file_manager | JSON 格式化 + 层级折叠 |
| 其他 | 纯文本 |

长结果（>200 行）默认截断，点击展开全量。

### 6.3 操作

- 错误状态「重试」= 重新生成整条消息（v2）
- 单工具精准重试 = v3 规划
- 「折叠全部」/「展开全部」总开关

### 6.4 容错

- version > 当前支持版本 → 降级为拼接所有 text segment 文本
- 未知 segment type → 忽略或渲染为纯文本

### 6.5 CSS

```css
.tool-seg {
  margin: 8px 0; padding: 8px 12px;
  background: rgba(124, 92, 252, 0.08);
  border-left: 3px solid var(--primary);
  border-radius: 0 8px 8px 0;
  font-size: 13px; position: relative;
}
.tool-seg + .tool-seg::before {
  content: ''; position: absolute;
  left: -3px; top: -8px; width: 3px; height: 8px;
  background: var(--primary);  /* JS 动态设置为相邻段状态色 */
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
| S0 | 后端 react.py 改为 segment yield + tool_call_id + done/error 事件 |
| S1 | 前端 chat store：appendSegment（状态优先级 + 组内排序）+ done/error 兜底 + 旧格式兼容 |
| S2 | 前端 ChatBubble：segments 渲染 + 时间线 + 结果格式化 + 重试 + 折叠 |
| S3 | 测试：并发工具、乱序、长消息、流式结束兜底、高版本降级 |
