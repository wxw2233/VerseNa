export function splitAgentSegments(segments = []) {
  let lastToolIndex = -1
  for (let index = segments.length - 1; index >= 0; index -= 1) {
    if (['tool', 'subagent', 'subagent_plan'].includes(segments[index]?.type)) {
      lastToolIndex = index
      break
    }
  }

  const work = []
  const answer = []
  segments.forEach((segment, index) => {
    if (!segment) return
    if (segment.type === 'choice') {
      answer.push(segment)
      return
    }
    if (segment.type !== 'text' || index <= lastToolIndex) work.push(segment)
    else answer.push(segment)
  })

  return { work, answer }
}

export function finalAnswerText(segments = []) {
  return splitAgentSegments(segments).answer
    .filter(segment => segment.type === 'text')
    .map(segment => segment.content || '')
    .join('')
}

const TEXT_CHOICE_PATTERN = /^\s*(?:[-*]\s+)?(?:\*\*)?([A-F])(?:\*\*)?\s*[.)、:：]\s*(.+?)\s*$/i
const CLOSING_PROMPT_PATTERN = /^\s*(?:请选择|请直接|你可以|告诉我|选好后|回复(?:我)?)/

function cleanChoiceText(value = '') {
  return String(value)
    .trim()
    .replace(/^(?:\*\*|__|`)+|(?:\*\*|__|`)+$/g, '')
    .trim()
}

function splitQuestionPrefix(lines) {
  const intro = [...lines]
  while (intro.length && !intro[intro.length - 1].trim()) intro.pop()
  if (!intro.length) return { before: '', question: '请选择一个选项' }

  let blockStart = intro.length - 1
  while (blockStart > 0 && intro[blockStart - 1].trim()) blockStart -= 1
  return {
    before: intro.slice(0, blockStart).join('\n').trim(),
    question: intro.slice(blockStart).join('\n').trim() || '请选择一个选项',
  }
}

export function inferTextChoice(segments = []) {
  if (segments.some(segment => segment?.type === 'choice')) return null
  const text = segments
    .filter(segment => segment?.type === 'text')
    .map(segment => segment.content || '')
    .join('')
    .trim()
  if (!text) return null

  const lines = text.split(/\r?\n/)
  const markers = []
  lines.forEach((line, index) => {
    const match = line.match(TEXT_CHOICE_PATTERN)
    if (match) markers.push({ index, id: match[1].toUpperCase(), label: cleanChoiceText(match[2]) })
  })
  if (markers.length < 2 || markers[0].id !== 'A') return null

  const consecutive = []
  for (const marker of markers) {
    const expected = String.fromCharCode(65 + consecutive.length)
    if (marker.id !== expected) break
    consecutive.push(marker)
  }
  if (consecutive.length < 2) return null

  const { before, question } = splitQuestionPrefix(lines.slice(0, consecutive[0].index))
  const options = []
  let afterStart = lines.length
  consecutive.forEach((marker, optionIndex) => {
    const nextIndex = consecutive[optionIndex + 1]?.index ?? lines.length
    let detailLines = lines.slice(marker.index + 1, nextIndex)
    if (optionIndex === consecutive.length - 1) {
      const closingIndex = detailLines.findIndex(line => CLOSING_PROMPT_PATTERN.test(line))
      if (closingIndex >= 0) {
        afterStart = marker.index + 1 + closingIndex
        detailLines = detailLines.slice(0, closingIndex)
      }
    }
    options.push({
      id: marker.id,
      label: marker.label,
      description: cleanChoiceText(detailLines.join(' ')),
    })
  })

  return {
    before,
    after: afterStart < lines.length ? lines.slice(afterStart).join('\n').trim() : '',
    choice: {
      type: 'choice',
      choice_id: 'inferred_text_choice',
      question,
      options,
      inferred: true,
    },
  }
}
