/**
 * Tests for reading prep plans in #144's format: which messages are such plans, and which
 * dish (and dish color) each line belongs to.
 */

import { describe, it, expect } from 'vitest'
import { isPrepPlan, parsePrepPlan } from './prepPlan'
import { LYRIC_PLAN, OLD_PLAN, PLAN } from './prepPlan.fixtures'

describe('isPrepPlan', () => {
  // A plan message with #144's heading is one, in either language's units
  it('recognizes plans in the new format', () => {
    expect(isPrepPlan(PLAN)).toBe(true)
    expect(isPrepPlan('📋 Kahvaltı (#4) — Prep Plan\n\n⏱ Plan (7 dk)\n  0:07  — Hazır! ✓')).toBe(true)
  })

  // Older plans, lyric fallbacks and other messages keep their plain look
  it('leaves older plans, lyrics and other messages alone', () => {
    expect(isPrepPlan(OLD_PLAN)).toBe(false)
    expect(isPrepPlan(LYRIC_PLAN)).toBe(false)
    expect(isPrepPlan('⏱ Plan (5 min)\n  0:00  — Eggs: Boil')).toBe(false)
    expect(isPrepPlan('')).toBe(false)
    expect(isPrepPlan(undefined)).toBe(false)
  })
})

describe('parsePrepPlan', () => {
  // Time lines name their dish before the first colon, ↳ lines take the dish above, and a dish
  // keeps its color when it comes back after another dish
  it('gives each line its dish color', () => {
    const lines = parsePrepPlan(PLAN)
    expect(lines.map(l => l.kind)).toEqual(['line', 'gap', 'line', 'body', 'body', 'body', 'body', 'body', 'body', 'body'])
    expect(lines.slice(3).map(l => l.color)).toEqual([1, 2, 2, 2, 1, 1, null])
    expect(lines[4]).toMatchObject({ dish: 'Greek omelette', before: '  0:03  — ', after: ': Whisk 3 eggs with 30 g feta' })
    expect(lines[6].dish).toBeUndefined()
    expect(lines.map(l => l.text ?? '').join('\n')).toBe(PLAN)
  })

  // Colors follow first appearance, and a fifth dish starts over at the first color
  it('reuses the first color for a fifth dish', () => {
    const dishes = ['Toast', 'Eggs', 'Porridge', 'Tea', 'Pancakes', 'Eggs']
    const text = '📋 Brunch — Prep Plan\n\n⏱ Plan (6 min)\n' +
      dishes.map((d, i) => `  0:0${i}  — ${d}: Step ${i}`).join('\n') + '\n  0:06  — Ready! ✓'
    expect(parsePrepPlan(text).filter(l => l.dish).map(l => l.color)).toEqual([1, 2, 3, 4, 1, 2])
  })
})
