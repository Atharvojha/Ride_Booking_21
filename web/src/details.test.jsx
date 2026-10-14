import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { Metadata } from './details'
it('shows only available feature flags and local inspection dates', () => {
  render(<Metadata data={{ features: { wifi: true, petFriendly: false }, inspectionRecords: [{ date: '2026-10-10T20:00:00Z', passed: true }] }} />)
  expect(screen.getByText('wifi')).toBeVisible(); expect(screen.queryByText('pet Friendly')).toBeNull()
  expect(screen.getByText(/11 Oct 2026/)).toBeVisible(); expect(screen.getByText('Yes')).toBeVisible()
})

it('lists checked items as text and shows the newest inspection first', () => {
  render(<Metadata data={{ features: {}, inspectionRecords: [
    { date: '2025-11-08T00:00:00Z', itemsChecked: ['tires', 'lights'], passed: true },
    { date: '2026-06-21T00:00:00Z', itemsChecked: ['brakes'], passed: false }] }} />)
  expect(screen.getByText('tires, lights')).toBeVisible(); expect(screen.queryByText(/\[/)).toBeNull()
  const first = screen.getByText('Inspection 1').closest('.inspection')
  expect(first).toHaveTextContent('brakes'); expect(first).toHaveTextContent(/21 Jun 2026/)
})
