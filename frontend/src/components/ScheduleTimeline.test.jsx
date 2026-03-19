/**
 * Tests for the ScheduleTimeline component.
 */

import { it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ScheduleTimeline from './ScheduleTimeline'

const SCHEDULE = {
  timeline: [
    { time: 0, label: 'eggs — crack', resource: 'hands', note: '' },
    { time: 2, label: 'eggs — fry', resource: 'stove', note: '' },
    { time: 0, label: 'bread — toast', resource: 'toaster', note: '' },
  ],
  makespan_min: 7,
}


it('renders nothing when schedule is null', () => {
  const { container } = render(<ScheduleTimeline schedule={null} />)
  expect(container).toBeEmptyDOMElement()
})

it('renders nothing when timeline is empty', () => {
  const { container } = render(<ScheduleTimeline schedule={{ timeline: [], makespan_min: 0 }} />)
  expect(container).toBeEmptyDOMElement()
})

it('renders each timeline entry label', () => {
  render(<ScheduleTimeline schedule={SCHEDULE} />)
  expect(screen.getByText('eggs — crack')).toBeInTheDocument()
  expect(screen.getByText('eggs — fry')).toBeInTheDocument()
  expect(screen.getByText('bread — toast')).toBeInTheDocument()
})

it('shows the total makespan', () => {
  render(<ScheduleTimeline schedule={SCHEDULE} />)
  expect(screen.getByText('Total: 7 min')).toBeInTheDocument()
})
