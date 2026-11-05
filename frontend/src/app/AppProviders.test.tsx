import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { AppProviders } from './AppProviders'

it('renders the application inside the query and theme providers', () => {
  const client = new QueryClient()
  render(
    <AppProviders client={client}>
      <p>Ready</p>
    </AppProviders>,
  )
  expect(screen.getByText('Ready')).toBeVisible()
})
