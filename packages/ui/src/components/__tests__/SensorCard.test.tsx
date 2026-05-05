import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SensorCard } from '../SensorCard'
import { wrap } from '../test-utils'

describe('SensorCard', () => {
  it('shows label, value, and unit', () => {
    render(wrap(<SensorCard label="온도" value={22.4} unit="°C" status="ok" />))
    expect(screen.getByText('온도')).toBeInTheDocument()
    expect(screen.getByText(/22\.4/)).toBeInTheDocument()
    expect(screen.getByText(/°C/)).toBeInTheDocument()
  })

  it('applies danger color when status=danger', () => {
    render(wrap(<SensorCard label="CO2" value={1600} unit="ppm" status="danger" />))
    const valueEl = screen.getByText(/1600/)
    expect(valueEl).toHaveStyle({ color: '#FF3B30' })
  })
})
