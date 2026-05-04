import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ActuatorToggle } from '../ActuatorToggle'
import { wrap } from '../test-utils'

describe('ActuatorToggle', () => {
  it('shows display name and state text', () => {
    render(wrap(<ActuatorToggle label="환기팬" state="on" onToggle={() => {}} />))
    expect(screen.getByText('환기팬')).toBeInTheDocument()
    expect(screen.getByText('켜짐')).toBeInTheDocument()
  })

  it('calls onToggle with opposite state when clicked', () => {
    const onToggle = vi.fn()
    render(wrap(<ActuatorToggle label="x" state="off" onToggle={onToggle} />))
    fireEvent.click(screen.getByLabelText('toggle-x'))
    expect(onToggle).toHaveBeenCalledWith('on')
  })

  it('does not call onToggle while loading', () => {
    const onToggle = vi.fn()
    render(wrap(<ActuatorToggle label="x" state="off" loading onToggle={onToggle} />))
    // Tamagui renders an extra disabled-mirror button when `disabled={true}`,
    // so multiple nodes share the aria-label. Click them all — every one
    // must respect the disabled state.
    screen.getAllByLabelText('toggle-x').forEach(fireEvent.click)
    expect(onToggle).not.toHaveBeenCalled()
  })
})
