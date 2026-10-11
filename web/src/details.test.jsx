import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { Metadata } from './details'
it('shows only available feature flags and local inspection dates', () => {
  render(<Metadata data={{ features: { wifi: true, petFriendly: false }, inspectionRecords: [{ date: '2026-10-10T20:00:00Z', passed: true }] }} />)
  expect(screen.getByText('wifi')).toBeVisible(); expect(screen.queryByText('pet Friendly')).toBeNull()
  expect(screen.getByText(/11 Oct 2026/)).toBeVisible(); expect(screen.getByText('Yes')).toBeVisible()
})
