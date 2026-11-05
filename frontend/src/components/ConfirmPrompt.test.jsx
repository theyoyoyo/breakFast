/**
 * Tests for the shared "Are you sure?" box: the question, Cancel then the action, and a red
 * action for a delete.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ConfirmPrompt from './ConfirmPrompt'
import { dangerBtn, confirmBtn } from './ConfirmPrompt.styles'

describe('ConfirmPrompt', () => {
  // The box asks its question with Cancel first and the action last, and each button does its job
  it('asks with Cancel then the action', () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(<ConfirmPrompt label="Delete all" message="Are you sure?" confirmLabel="Delete" onConfirm={onConfirm} onCancel={onCancel} />)
    const prompt = screen.getByRole('alertdialog', { name: 'Delete all' })
    expect(prompt).toHaveTextContent('Are you sure?')
    expect([...prompt.querySelectorAll('button')].map(b => b.textContent)).toEqual(['Cancel', 'Delete'])
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  // A delete's action button is red, any other action uses the theme color
  it('makes a delete red', () => {
    const { rerender } = render(<ConfirmPrompt label="x" message="?" confirmLabel="Delete" danger onConfirm={() => {}} onCancel={() => {}} />)
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveStyle({ background: dangerBtn.background })
    rerender(<ConfirmPrompt label="x" message="?" confirmLabel="Allow" onConfirm={() => {}} onCancel={() => {}} />)
    expect(screen.getByRole('button', { name: 'Allow' }).style.background).toBe(confirmBtn.background)
    expect(confirmBtn.background).toBe('var(--secondary)')
  })
})
