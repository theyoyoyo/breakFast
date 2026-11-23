/**
 * Tests for the minimal Markdown renderer used in assistant chat messages.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MarkdownText, { parseMarkdown } from './MarkdownText'

describe('parseMarkdown', () => {
  // Markdown headings from the model become heading blocks, with the # marks dropped
  it('turns ### lines into headings without the hashes', () => {
    expect(parseMarkdown('### World Breakfast')).toEqual([{ type: 'heading', text: 'World Breakfast' }])
  })

  // Every bullet style the model uses joins one list, and a numbered list keeps its first number
  it('groups consecutive bullets and numbered items into lists', () => {
    const blocks = parseMarkdown('- Toast\n* Olives\n• Tea\n3. Boil\n4) Peel')
    expect(blocks).toEqual([
      { type: 'list', ordered: false, start: 1, items: ['Toast', 'Olives', 'Tea'] },
      { type: 'list', ordered: true, start: 3, items: ['Boil', 'Peel'] },
    ])
  })

  // Runs of blank lines become one gap, so a reply never opens or ends with empty space
  it('collapses blank lines and drops them at the start and end', () => {
    const blocks = parseMarkdown('\n\nFirst\n\n\n\nSecond\n\n')
    expect(blocks.map(b => b.type)).toEqual(['line', 'gap', 'line'])
  })

  // Prep plan lines start with spaces and a time, which must not be read as Markdown
  it('keeps prep-plan timeline lines as plain lines', () => {
    const blocks = parseMarkdown('  0:00  — Boil eggs (7 min)  [Stove]\n         ↳ Drain')
    expect(blocks.map(b => b.type)).toEqual(['line', 'line'])
  })

  // A line of dashes or spaced stars is a rule, not an empty bullet
  it('recognizes horizontal rules before bullets', () => {
    expect(parseMarkdown('---')).toEqual([{ type: 'rule' }])
    expect(parseMarkdown('* * *')).toEqual([{ type: 'rule' }])
  })
})

describe('MarkdownText', () => {
  // The user sees formatting, never the raw # and * characters
  it('renders headings, bold and italic instead of the symbols', () => {
    const { container } = render(<MarkdownText text={'### Menu\nTry the **Tost** with *fresh* tea.'} />)
    expect(screen.getByRole('heading', { name: 'Menu' })).toBeInTheDocument()
    expect(container.querySelector('strong')).toHaveTextContent('Tost')
    expect(container.querySelector('em')).toHaveTextContent('fresh')
    expect(container.textContent).not.toMatch(/[#*]/)
  })

  // Bold text inside a list item is rendered like anywhere else
  it('renders list items with inline formatting', () => {
    render(<MarkdownText text={'- **Menemen** with peppers\n- Olives'} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0].querySelector('strong')).toHaveTextContent('Menemen')
  })

  // Stars used as multiplication stay text instead of starting italics
  it('leaves stars with spaces around them alone', () => {
    const { container } = render(<MarkdownText text="2 * 3 * 4" />)
    expect(container.querySelector('em')).toBeNull()
    expect(container).toHaveTextContent('2 * 3 * 4')
  })

  // A half-streamed bold marker shows as typed until its closing marker arrives
  it('shows unclosed markers as text while a reply is still streaming', () => {
    const { container } = render(<MarkdownText text="Try the **Tos" />)
    expect(container.querySelector('strong')).toBeNull()
    expect(container).toHaveTextContent('Try the **Tos')
  })

  // Model output is text only: HTML in a reply is shown, never rendered
  it('never turns model output into HTML elements', () => {
    const { container } = render(<MarkdownText text={'<img src=x onerror=alert(1)> **<b>hi</b>**'} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(container).toHaveTextContent('<img src=x onerror=alert(1)>')
  })
})
