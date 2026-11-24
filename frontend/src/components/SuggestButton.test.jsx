/**
 * Tests for the Suggest button: a tap suggests, a long press reveals Favorites and Explore,
 * a pick suggests in that mode, and a tap outside closes the menu.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import SuggestButton from './SuggestButton'

const button = () => screen.getByRole('button', { name: 'Suggest breakfast' })

// Hold the button for the long press
function longPress() {
  vi.useFakeTimers()
  fireEvent.pointerDown(button())
  act(() => vi.advanceTimersByTime(1000))
  fireEvent.pointerUp(button())
  fireEvent.click(button())
  vi.useRealTimers()
}

describe('SuggestButton', () => {
  afterEach(() => vi.useRealTimers())

  // A short tap suggests a breakfast with no mode, on its click
  it('suggests on a tap', () => {
    const onSuggest = vi.fn()
    render(<SuggestButton onSuggest={onSuggest} />)
    fireEvent.pointerDown(button())
    fireEvent.pointerUp(button())
    expect(onSuggest).not.toHaveBeenCalled()
    fireEvent.click(button())
    expect(onSuggest).toHaveBeenCalledTimes(1)
    expect(onSuggest).toHaveBeenCalledWith()
  })

  // Enter or Space on the focused button clicks it with no pointer behind, and suggests too
  it('suggests from the keyboard', () => {
    const onSuggest = vi.fn()
    render(<SuggestButton onSuggest={onSuggest} />)
    fireEvent.click(button(), { detail: 0 })
    expect(onSuggest).toHaveBeenCalledTimes(1)
  })

  // A long press reveals the two modes instead of suggesting, and a pick suggests in that mode
  it('reveals the modes on a long press', () => {
    const onSuggest = vi.fn()
    render(<SuggestButton onSuggest={onSuggest} />)
    longPress()
    expect(onSuggest).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Explore world cuisines' }))
    expect(onSuggest).toHaveBeenCalledWith('explore')
    expect(screen.queryByRole('button', { name: 'Suggest from favorites' })).toBeNull()
  })

  // A tap on the dimmed backdrop closes the modes without suggesting
  it('closes the modes on a tap outside', () => {
    const onSuggest = vi.fn()
    render(<SuggestButton onSuggest={onSuggest} />)
    longPress()
    fireEvent.click(screen.getByTestId('suggest-backdrop'))
    expect(screen.queryByRole('button', { name: 'Suggest from favorites' })).toBeNull()
    expect(onSuggest).not.toHaveBeenCalled()
  })

  // A disabled button neither suggests nor opens the modes
  it('does nothing while disabled', () => {
    const onSuggest = vi.fn()
    render(<SuggestButton onSuggest={onSuggest} disabled />)
    longPress()
    fireEvent.click(button())
    expect(onSuggest).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Explore world cuisines' })).toBeNull()
  })
})
