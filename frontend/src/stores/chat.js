import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const isStopping = ref(false)
  const activeGenerationId = ref(null)
  const currentPersona = ref('default')
  const bgOpacity = ref(0.3)

  const statusPriority = { running: 1, done: 2, stopped: 3, error: 4 }

  function addUserMessage(content, dbId, clientMessageId, reasoningEnabled = false, reasoningEffort = null) {
    messages.value.push({
      role: 'user',
      content,
      streaming: false,
      dbId: dbId || null,
      clientMessageId: clientMessageId || null,
      reasoningEnabled,
      reasoningEffort,
    })
  }

  function startStreaming(generationId, reasoningEnabled = false) {
    activeGenerationId.value = generationId || null
    isStreaming.value = true
    isStopping.value = false
    messages.value.push({
      role: 'assistant',
      version: 2,
      segments: [],
      expandedTools: {},
      streaming: true,
      emoji: null,
      generationId: generationId || null,
      reasoningEnabled,
    })
  }

  function generationMatches(generationId) {
    return !generationId || generationId === activeGenerationId.value
  }

  function activeAssistantIndex(generationId) {
    if (!generationId) return messages.value.length - 1
    return messages.value.findLastIndex(
      message => message.role === 'assistant' && message.generationId === generationId,
    )
  }

  function appendSegment(segment, generationId) {
    if (!generationMatches(generationId)) return false
    const targetIndex = activeAssistantIndex(generationId)
    const last = messages.value[targetIndex]

    if (!last || last.role !== 'assistant' || !last.streaming) {
      // 新建 assistant 消息
      if (segment.type === 'text' && !segment.content) return  // 空片段过滤
      messages.value.push({
        role: 'assistant',
        version: 2,
        segments: [{ ...segment }],
        expandedTools: {},
        streaming: true,
        emoji: null,
        generationId: generationId || null,
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
      } else if (segment.type === 'reasoning') {
        const idx = segs.findIndex(
          s => s.type === 'reasoning' && s.reasoning_id === segment.reasoning_id,
        )
        if (idx >= 0) {
          const existing = segs[idx]
          segs[idx] = {
            ...existing,
            ...segment,
            content: (existing.content || '') + (segment.content || ''),
          }
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
      } else if (segment.type === 'subagent') {
        const idx = segs.findIndex(s => (
          s.type === 'subagent' && s.subagent_id === segment.subagent_id
        ))
        if (idx >= 0) segs[idx] = { ...segs[idx], ...segment }
        else segs.push({ ...segment })
      } else if (segment.type === 'subagent_plan') {
        const idx = segs.findIndex(s => (
          s.type === 'subagent_plan' && s.plan_id === segment.plan_id
        ))
        if (idx >= 0) segs[idx] = { ...segs[idx], ...segment }
        else segs.push({ ...segment })
      } else if (segment.type === 'choice') {
        const idx = segs.findIndex(s => (
          s.type === 'choice' && s.choice_id === segment.choice_id
        ))
        if (idx >= 0) segs[idx] = { ...segs[idx], ...segment }
        else segs.push({ ...segment })
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

      messages.value[targetIndex] = { ...last, segments: sorted }
    }
    return true
  }

  function finishStreaming(emoji, generationId) {
    if (!generationMatches(generationId)) return false
    isStreaming.value = false
    isStopping.value = false
    const targetIndex = activeAssistantIndex(generationId)
    const last = messages.value[targetIndex]
    if (last && last.role === 'assistant') {
      // 兜底：残留 running → error
      const segs = last.segments.map(s => {
        if (s.type === 'tool' && s.status === 'running') {
          return { ...s, status: 'error', result_summary: '执行超时或断流' }
        }
        if (s.type === 'reasoning' && s.status === 'running') {
          return { ...s, status: 'done' }
        }
        if (s.type === 'subagent' && s.status === 'running') {
          return { ...s, status: 'error', detail: '子代理状态未正常结束' }
        }
        if (s.type === 'subagent_plan' && s.status === 'running') {
          return { ...s, status: 'partial', detail: '任务计划状态未正常结束' }
        }
        return s
      })
      last.segments = segs
      last.streaming = false
      if (emoji) last.emoji = emoji
    }
    activeGenerationId.value = null
    return true
  }

  function handleError(message, generationId) {
    if (!generationMatches(generationId)) return false
    isStreaming.value = false
    isStopping.value = false
    const targetIndex = activeAssistantIndex(generationId)
    const last = messages.value[targetIndex]
    if (last && last.role === 'assistant') {
      // 兜底残留 running → error
      const segs = last.segments.map(s => {
        if (s.type === 'tool' && s.status === 'running') {
          return { ...s, status: 'error', result_summary: '服务异常，执行中断' }
        }
        if (s.type === 'reasoning' && s.status === 'running') {
          return { ...s, status: 'error' }
        }
        if (s.type === 'subagent' && s.status === 'running') {
          return { ...s, status: 'error', detail: '服务异常，子代理执行中断' }
        }
        if (s.type === 'subagent_plan' && s.status === 'running') {
          return { ...s, status: 'partial', detail: '服务异常，任务计划执行中断' }
        }
        return s
      })
      // 追加错误 text 段
      segs.push({ type: 'text', content: `⚠️ ${message}` })
      last.segments = segs
      last.streaming = false
    }
    activeGenerationId.value = null
    return true
  }

  function clearMessages() {
    messages.value = []
    isStreaming.value = false
    isStopping.value = false
    activeGenerationId.value = null
  }

  function requestStop(generationId) {
    if (!isStreaming.value || generationId !== activeGenerationId.value) return false
    isStopping.value = true
    return true
  }

  function loadHistory(history) {
    clearMessages()
    for (const message of history) {
      if (message.role === 'user') {
        addUserMessage(
          message.content,
          message.id,
          message.client_message_id,
          message.reasoning_enabled === true,
          message.reasoning_effort || null,
        )
        continue
      }
      if (message.role !== 'assistant') continue

      const restored = {
        role: 'assistant',
        streaming: false,
        dbId: message.id,
        generationId: message.generation_id || null,
        reasoningEnabled: message.reasoning_enabled === true,
        reasoningEffort: message.reasoning_effort || null,
        reasoningModel: message.reasoning_model || null,
        reasoningDurationMs: message.reasoning_duration_ms || 0,
      }
      if (message.segments?.length) {
        restored.segments = message.content && message.segments.every(
          segment => !['text', 'choice'].includes(segment.type),
        )
          ? [...message.segments, { type: 'text', content: message.content }]
          : message.segments
        restored.version = message.version || 2
        restored.expandedTools = {}
      } else {
        restored.content = message.content || ''
      }
      if (message.emoji) restored.emoji = message.emoji
      messages.value.push(restored)
    }
  }

  function deleteFrom(index) {
    messages.value.splice(index)
  }

  return {
    messages, isStreaming, isStopping, activeGenerationId, currentPersona, bgOpacity,
    addUserMessage, startStreaming, appendSegment, finishStreaming, handleError, clearMessages, loadHistory, requestStop,
    deleteFrom,
  }
})
