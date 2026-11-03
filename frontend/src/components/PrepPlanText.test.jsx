/**
 * Tests for the prep plan renderer: each dish's lines get a bar in its color, the dish name on a
 * time line takes the color, and the text reads exactly as the plan was written.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PrepPlanText from './PrepPlanText'
import { PLAN } from '../utils/prepPlan.fixtures'

describe('PrepPlanText', () => {
  // Every step line has its dish's bar, ↳ lines included; the Ready line keeps a clear bar to line up
  it('draws a bar in the dish color beside each line', () => {
    const { container } = render(<div><PrepPlanText text={PLAN} /></div>)
    const bars = [...container.firstChild.children].map(el => el.style.borderLeftColor)
    expect(bars).toEqual([
      '', '', '',
      'var(--dish-1)', 'var(--dish-2)', 'var(--dish-2)', 'var(--dish-2)', 'var(--dish-1)', 'var(--dish-1)',
      'transparent',
    ])
  })

  // The dish name takes the color and the step text keeps the normal color
  it('colors the dish name only', () => {
    render(<PrepPlanText text={PLAN} />)
    const names = screen.getAllByText('Greek omelette')
    expect(names).toHaveLength(1)
    expect(names[0].style.color).toBe('var(--dish-2)')
    expect(screen.getByText(': Whisk 3 eggs with 30 g feta', { exact: false }).style.color).toBe('')
  })

  // Nothing is added to the text, so copying the plan reads as before
  it('shows the plan text as written', () => {
    const { container } = render(<div><PrepPlanText text={PLAN} /></div>)
    const shown = [...container.firstChild.children].map(el => el.textContent).join('\n')
    expect(shown).toBe(PLAN)
  })
})
