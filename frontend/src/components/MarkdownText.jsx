import * as s from './MarkdownText.styles'

/**
 * Minimal Markdown for assistant messages: headings, **bold**, *italic*,
 * bullet and numbered lists, and horizontal rules.
 *
 * Builds React elements only, never HTML strings, so model output can't
 * inject markup. Anything else (tables, links, code) is shown as plain text.
 */

const RULE_RE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/
const HEADING_RE = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/
const BULLET_RE = /^\s*[-*•]\s+(.*)$/
const NUMBERED_RE = /^\s*(\d+)[.)]\s+(.*)$/
// **bold**, or *italic* with no space just inside the stars (so "2 * 3 * 4" stays as is)
const INLINE_RE = /(\*\*[^*\n]+?\*\*|\*[^*\s](?:[^*\n]*?[^*\s])?\*)/g

export function parseMarkdown(text) {
  const blocks = []
  const addListItem = (ordered, start, itemText) => {
    const last = blocks[blocks.length - 1]
    if (last?.type === 'list' && last.ordered === ordered) last.items.push(itemText)
    else blocks.push({ type: 'list', ordered, start, items: [itemText] })
  }

  for (const line of (text || '').split('\n')) {
    let m
    if (RULE_RE.test(line)) {
      blocks.push({ type: 'rule' })
    } else if ((m = line.match(HEADING_RE))) {
      blocks.push({ type: 'heading', text: m[1] })
    } else if ((m = line.match(BULLET_RE))) {
      addListItem(false, 1, m[1])
    } else if ((m = line.match(NUMBERED_RE))) {
      addListItem(true, Number(m[1]), m[2])
    } else if (!line.trim()) {
      if (blocks.length && blocks[blocks.length - 1].type !== 'gap') blocks.push({ type: 'gap' })
    } else {
      blocks.push({ type: 'line', text: line })
    }
  }

  if (blocks[blocks.length - 1]?.type === 'gap') blocks.pop()
  return blocks
}

export function renderInline(text) {
  // split() with one capture group puts the matches at odd indexes
  return text.split(INLINE_RE).map((part, i) => {
    if (i % 2 === 0) return part
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
    return <em key={i}>{part.slice(1, -1)}</em>
  })
}

export default function MarkdownText({ text }) {
  return parseMarkdown(text).map((block, i) => {
    switch (block.type) {
      case 'heading':
        return <div key={i} role="heading" aria-level={3} style={s.heading(i === 0)}>{renderInline(block.text)}</div>
      case 'list': {
        const List = block.ordered ? 'ol' : 'ul'
        return (
          <List key={i} start={block.ordered ? block.start : undefined} style={s.list}>
            {block.items.map((item, j) => <li key={j} style={s.listItem}>{renderInline(item)}</li>)}
          </List>
        )
      }
      case 'rule':
        return <hr key={i} style={s.rule} />
      case 'gap':
        return <div key={i} style={s.gap} />
      default:
        return <div key={i}>{renderInline(block.text)}</div>
    }
  })
}
