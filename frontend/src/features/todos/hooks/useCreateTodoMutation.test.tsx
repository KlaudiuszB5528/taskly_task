import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, act } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import { todoKeys } from '../api/queryKeys'
import { todosApi } from '../api/todos'
import { useCreateTodoMutation } from './useCreateTodoMutation'

vi.mock('../api/todos', () => ({
  todosApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}))

function renderCreate() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  })
  const view = renderHook(() => useCreateTodoMutation(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  })
  return { client, ...view }
}

it('prepends the saved task and replaces a stale copy of the same id', async () => {
  const saved = { ...todoFixture, title: 'Saved' }
  const other = { ...todoFixture, id: 8, title: 'Other' }
  vi.mocked(todosApi.create).mockResolvedValue(saved)
  const { client, result } = renderCreate()
  client.setQueryData(todoKeys.list, [
    { ...todoFixture, title: 'Stale' },
    other,
  ])
  const cancel = vi.spyOn(client, 'cancelQueries')

  await act(async () => {
    await result.current.mutateAsync(todoFixture)
  })

  expect(cancel).toHaveBeenCalledWith({ queryKey: todoKeys.list })
  expect(client.getQueryData(todoKeys.list)).toEqual([saved, other])
})

it('starts the list with the saved task when the cache is empty', async () => {
  vi.mocked(todosApi.create).mockResolvedValue(todoFixture)
  const { client, result } = renderCreate()
  await act(async () => {
    await result.current.mutateAsync(todoFixture)
  })
  expect(client.getQueryData(todoKeys.list)).toEqual([todoFixture])
})
