// Prep plans in #144's format: one list in time order under the "⏱ Plan (…)" heading, each time
// line naming its dish before the first colon and ↳ lines going on with the dish above. The chat
// colors these by dish (#145); older plans and lyric fallbacks aren't in this format.

// A prep-plan message: "📋 {meal} — Prep Plan" (ChatInterface.jsx, handleSchedule), then the plan
const TITLE_RE = /^📋 .* — Prep Plan$/
// The heading the backend writes in every language (routers/scheduler.py, _PLAN_LABELS)
const HEADING_RE = /^⏱ Plan \(\d+ \S+\)$/
// "  0:05  — Greek omelette: Whisk 3 eggs": the time, then the rest of the line
const TIME_RE = /^(\s*\d+:\d{2}\s+—\s+)(.*)$/
const STEP_RE = /^\s*↳/

// Dish colors per theme (--dish-1 … --dish-4 in index.css); a fifth dish starts over at the first
export const DISH_COLORS = 4

export function isPrepPlan(text) {
  const lines = (text || '').split('\n')
  return TITLE_RE.test(lines[0]) && lines.some(line => HEADING_RE.test(line))
}

/**
 * The lines of a plan, each one of:
 * - { kind: 'gap' } for a blank line;
 * - { kind: 'line', text } for the title and heading;
 * - { kind: 'body', text, color } for a step or the Ready line, color 1–4 (null on the Ready line),
 *   plus { dish, before, after } on a time line: the text around the dish name.
 * Dishes take the colors in order of first appearance, and ↳ lines take the dish above.
 */
export function parsePrepPlan(text) {
  const colors = new Map()
  let above = null
  return text.split('\n').map(line => {
    if (!line.trim()) return { kind: 'gap' }
    const time = line.match(TIME_RE)
    if (time) {
      const colon = time[2].indexOf(':')
      if (colon === -1) {
        above = null
        return { kind: 'body', text: line, color: null }
      }
      const dish = time[2].slice(0, colon)
      if (!colors.has(dish)) colors.set(dish, (colors.size % DISH_COLORS) + 1)
      above = { kind: 'body', text: line, color: colors.get(dish), dish, before: time[1], after: time[2].slice(colon) }
      return above
    }
    if (STEP_RE.test(line)) return { kind: 'body', text: line, color: above?.color ?? null }
    return { kind: 'line', text: line }
  })
}
