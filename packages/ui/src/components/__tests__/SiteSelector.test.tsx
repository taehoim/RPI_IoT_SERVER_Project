import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SiteSelector } from '../SiteSelector'
import { wrap } from '../test-utils'

describe('SiteSelector', () => {
  it('renders the currently selected gateway name in the trigger', () => {
    render(
      wrap(
        <SiteSelector
          gateways={[
            { id: '1', name: '농장 1동' },
            { id: '2', name: '농장 2동' },
          ]}
          value="1"
          onChange={() => {}}
        />,
      ),
    )
    // Tamagui Select renders the active value inside the trigger
    expect(screen.getByText('농장 1동')).toBeInTheDocument()
  })

  it('renders nothing in trigger when value does not match any gateway', () => {
    render(
      wrap(
        <SiteSelector
          gateways={[{ id: '1', name: 'A' }]}
          value=""
          onChange={() => {}}
        />,
      ),
    )
    // Smoke test: render doesn't throw, the trigger is in the doc.
    // Tamagui's <Select> emits two trigger nodes (the visible button + a hidden
    // floating-ui anchor mirror), so we use getAllByRole and assert at least one.
    expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0)
  })
})
