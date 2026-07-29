const BRACKETED_TEXT = /（[^（）]*）|\([^()]*\)|【[^【】]*】|\[[^\[\]]*\]|［[^［］]*］|\{[^{}]*\}|｛[^｛｝]*｝/g

function stripBracketedText(text) {
  let result = text
  let previous
  do {
    previous = result
    result = result.replace(BRACKETED_TEXT, '')
  } while (result !== previous)
  return result
}

export function prepareTextForSpeech(value) {
  if (!value) return ''

  let text = String(value)
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]+>/g, '')
    .replace(/\*\*([\s\S]*?)\*\*/g, '$1')
    .replace(/__([\s\S]*?)__/g, '$1')
    .replace(/\*(?!\s)([\s\S]*?\S)\*/g, '')
    .replace(/_([^_\n]+)_/g, '$1')

  text = stripBracketedText(text)

  return text
    .replace(/^[>#]+\s*/gm, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\s+([，。！？；：,.!?;:])/g, '$1')
    .replace(/\n{2,}/g, '\n')
    .trim()
}
