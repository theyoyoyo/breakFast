/**
 * Tests for the chat bar's mic: until voice input is ready, a tap on it says "Available soon!" for a
 * moment, and it shows only while the box is empty.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import ChatBar from './ChatBar'

function renderBar(input = '') {
  render(
    <ChatBar
      input={input}
      onInputChange={vi.fn()}
      onKeyDown={vi.fn()}
      onSend={vi.fn()}
      onStop={vi.fn()}
      busy={false}
      onSuggest={vi.fn()}
      suggestDisabled={false}
      onTodayIAte={vi.fn()}
    />,
  )
}

describe('ChatBar mic', () => {
  afterEach(() => vi.useRealTimers())

  // A tap on the mic shows the note, and the note goes by itself after two seconds
  it('says available soon for a moment', () => {
    vi.useFakeTimers()
    renderBar()
    fireEvent.click(screen.getByRole('button', { name: 'Voice input' }))
    expect(screen.getByRole('status')).toHaveTextContent('Available soon!')
    act(() => vi.advanceTimersByTime(2000))
    expect(screen.queryByText('Available soon!')).toBeNull()
  })

  // While the box has text the mic makes room for it, and Send takes the cloche's place
  it('hides the mic while the box has text', () => {
    renderBar('Eggs')
    expect(screen.queryByRole('button', { name: 'Voice input' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument()
  })
})
