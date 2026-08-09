export function splitAgentSegments(segments = []) {
  let lastToolIndex = -1
  for (let index = segments.length - 1; index >= 0; index -= 1) {
    if (segments[index]?.type === 'tool') {
      lastToolIndex = index
      break
    }
  }

  const work = []
  const answer = []
  segments.forEach((segment, index) => {
    if (!segment) return
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
