import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const currentPersona = ref('default')
  const bgOpacity = ref(0.3)

  const statusPriority = { running: 1, done: 2, error: 3 }

  function addUserMessage(content) {
    messages.value.push({
      role: 'user',
      content,
      streaming: false
    })
  }

  function appendSegment(segment) {
    const last = messages.value[messages.value.length - 1]

    if (!last || last.role !== 'assistant' || !last.streaming) {
      // 新建 assistant 消息
      if (segment.type === 'text' && !segment.content) return  // 空片段过滤
      messages.value.push({
        role: 'assistant',
        version: 2,
        segments: [{ ...segment }],
        expandedTools: {},
        streaming: true,
        emoji: null
      })
    } else {
      // 追加到现有消息
      const segs = [...last.segments]

      if (segment.type === 'text') {
        if (!segment.content) return  // 空片段过滤
        const lastSeg = segs[segs.length - 1]
        if (lastSeg && lastSeg.type === 'text') {
          // 合并连续 text segment
          segs[segs.length - 1] = { ...lastSeg, content: lastSeg.content + segment.content }
        } else {
          segs.push({ ...segment })
        }
      } else if (segment.type === 'tool') {
        const idx = segs.findIndex(s => s.type === 'tool' && s.tool_call_id === segment.tool_call_id)
        if (idx >= 0) {
          // 状态优先级：仅高优先级覆盖低优先级
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

      messages.value[messages.value.length - 1] = { ...last, segments: sorted }
    }
  }

  function finishStreaming(emoji) {
    isStreaming.value = false
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      // 兜底：残留 running → error
      const segs = last.segments.map(s => {
        if (s.type === 'tool' && s.status === 'running') {
          return { ...s, status: 'error', result_summary: '执行超时或断流' }
        }
        return s
      })
      last.segments = segs
      last.streaming = false
      if (emoji) last.emoji = emoji
    }
  }

  function handleError(message) {
    isStreaming.value = false
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      // 兜底残留 running → error
      const segs = last.segments.map(s => {
        if (s.type === 'tool' && s.status === 'running') {
          return { ...s, status: 'error', result_summary: '服务异常，执行中断' }
        }
        return s
      })
      // 追加错误 text 段
      segs.push({ type: 'text', content: `⚠️ ${message}` })
      last.segments = segs
      last.streaming = false
    }
  }

  function clearMessages() {
    messages.value = []
    isStreaming.value = false
  }

  return {
    messages, isStreaming, currentPersona, bgOpacity,
    addUserMessage, appendSegment, finishStreaming, handleError, clearMessages
  }
})
