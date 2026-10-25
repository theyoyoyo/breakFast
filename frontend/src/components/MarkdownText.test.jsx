/**
 * Tests for the minimal Markdown renderer used in assistant chat messages.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MarkdownText, { parseMarkdown } from './MarkdownText'

describe('parseMarkdown', () => {
  it('turns ### lines into headings without the hashes', () => {
    expect(parseMarkdown('### World Breakfast')).toEqual([{ type: 'heading', text: 'World Breakfast' }])
  })

  it('groups consecutive bullets and numbered items into lists', () => {
    const blocks = parseMarkdown('- Toast\n* Olives\n• Tea\n3. Boil\n4) Peel')
    expect(blocks).toEqual([
      { type: 'list', ordered: false, start: 1, items: ['Toast', 'Olives', 'Tea'] },
      { type: 'list', ordered: true, start: 3, items: ['Boil', 'Peel'] },
    ])
  })

  it('collapses blank lines and drops them at the start and end', () => {
    const blocks = parseMarkdown('\n\nFirst\n\n\n\nSecond\n\n')
    expect(blocks.map(b => b.type)).toEqual(['line', 'gap', 'line'])
  })

  it('keeps prep-plan timeline lines as plain lines', () => {
    const blocks = parseMarkdown('  0:00  — Boil eggs (7 min)  [Stove]\n         ↳ Drain')
    expect(blocks.map(b => b.type)).toEqual(['line', 'line'])
  })

  it('recognizes horizontal rules before bullets', () => {
    expect(parseMarkdown('---')).toEqual([{ type: 'rule' }])
    expect(parseMarkdown('* * *')).toEqual([{ type: 'rule' }])
  })
})

describe('MarkdownText', () => {
  it('renders headings, bold and italic instead of the symbols', () => {
    const { container } = render(<MarkdownText text={'### Menu\nTry the **Tost** with *fresh* tea.'} />)
    expect(screen.getByRole('heading', { name: 'Menu' })).toBeInTheDocument()
    expect(container.querySelector('strong')).toHaveTextContent('Tost')
    expect(container.querySelector('em')).toHaveTextContent('fresh')
    expect(container.textContent).not.toMatch(/[#*]/)
  })

  it('renders list items with inline formatting', () => {
    render(<MarkdownText text={'- **Menemen** with peppers\n- Olives'} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0].querySelector('strong')).toHaveTextContent('Menemen')
  })

  it('leaves stars with spaces around them alone', () => {
    const { container } = render(<MarkdownText text="2 * 3 * 4" />)
    expect(container.querySelector('em')).toBeNull()
    expect(container).toHaveTextContent('2 * 3 * 4')
  })

  it('shows unclosed markers as text while a reply is still streaming', () => {
    const { container } = render(<MarkdownText text="Try the **Tos" />)
    expect(container.querySelector('strong')).toBeNull()
    expect(container).toHaveTextContent('Try the **Tos')
  })

  it('never turns model output into HTML elements', () => {
    const { container } = render(<MarkdownText text={'<img src=x onerror=alert(1)> **<b>hi</b>**'} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(container).toHaveTextContent('<img src=x onerror=alert(1)>')
  })
})
