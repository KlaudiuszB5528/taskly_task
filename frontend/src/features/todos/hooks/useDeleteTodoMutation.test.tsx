import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import { todoKeys } from '../api/queryKeys'
import { todosApi } from '../api/todos'
import { useDeleteTodoMutation } from './useDeleteTodoMutation'

vi.mock('../api/todos', () => ({
  todosApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}))

it('removes the deleted task from the cached list', async () => {
  const other = { ...todoFixture, id: 8, title: 'Other' }
  vi.mocked(todosApi.remove).mockResolvedValue(undefined)
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  client.setQueryData(todoKeys.list, [todoFixture, other])
  const cancel = vi.spyOn(client, 'cancelQueries')
  const { result } = renderHook(() => useDeleteTodoMutation(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  })

  await act(async () => {
    await result.current.mutateAsync(todoFixture.id)
  })

  expect(cancel).toHaveBeenCalledWith({ queryKey: todoKeys.list })
  expect(todosApi.remove).toHaveBeenCalledWith(todoFixture.id)
  expect(client.getQueryData(todoKeys.list)).toEqual([other])
})
