import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, it, vi } from 'vitest'
import { todosApi } from '../api/todos'
import { useDeleteTodoMutation } from './useDeleteTodoMutation'
import { useTodosBusy } from './useTodosBusy'

vi.mock('../api/todos', () => ({
  todosApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}))

it('is true only while a task mutation is running', async () => {
  let finish: () => void = () => {}
  vi.mocked(todosApi.remove).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = () => resolve(undefined)
      }),
  )
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  const { result } = renderHook(
    () => ({ busy: useTodosBusy(), remove: useDeleteTodoMutation() }),
    {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    },
  )
  expect(result.current.busy).toBe(false)

  act(() => {
    result.current.remove.mutate(7)
  })
  await waitFor(() => expect(result.current.busy).toBe(true))

  await act(async () => {
    finish()
  })
  await waitFor(() => expect(result.current.busy).toBe(false))
})
