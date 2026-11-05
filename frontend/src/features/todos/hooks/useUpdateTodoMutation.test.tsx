import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import { todoKeys } from '../api/queryKeys'
import { todosApi } from '../api/todos'
import { useUpdateTodoMutation } from './useUpdateTodoMutation'

vi.mock('../api/todos', () => ({
  todosApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}))

it('replaces only the task that was saved', async () => {
  const saved = { ...todoFixture, title: 'Renamed' }
  const other = { ...todoFixture, id: 8, title: 'Other' }
  vi.mocked(todosApi.update).mockResolvedValue(saved)
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  client.setQueryData(todoKeys.list, [todoFixture, other])
  const { result } = renderHook(() => useUpdateTodoMutation(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  })

  await act(async () => {
    await result.current.mutateAsync({
      id: todoFixture.id,
      input: { title: 'Renamed' },
    })
  })

  expect(todosApi.update).toHaveBeenCalledWith(todoFixture.id, {
    title: 'Renamed',
  })
  expect(client.getQueryData(todoKeys.list)).toEqual([saved, other])
})
