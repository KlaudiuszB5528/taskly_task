import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { todoFixture } from '../../test/todoFixture'
import { useNotice } from '../../hooks/useNotice'
import { useTodoFilters } from './hooks/useTodoFilters'
import { useTodosBusy } from './hooks/useTodosBusy'
import { useTodosQuery } from './hooks/useTodosQuery'
import { useUpdateTodoMutation } from './hooks/useUpdateTodoMutation'
import { TodosPage } from './TodosPage'

vi.mock('../../design-system', () => import('../../design-system/mocks'))
vi.mock('../../hooks/useNotice', () => ({ useNotice: vi.fn() }))
vi.mock('./hooks/useTodoFilters', () => ({ useTodoFilters: vi.fn() }))
vi.mock('./hooks/useTodosBusy', () => ({ useTodosBusy: vi.fn() }))
vi.mock('./hooks/useTodosQuery', () => ({ useTodosQuery: vi.fn() }))
vi.mock('./hooks/useUpdateTodoMutation', () => ({
  useUpdateTodoMutation: vi.fn(),
}))
vi.mock('./components/TodosHeader', () => ({
  TodosHeader: ({
    disabled,
    onCreate,
  }: {
    disabled: boolean
    onCreate: () => void
  }) => (
    <button type="button" disabled={disabled} onClick={onCreate}>
      Create task
    </button>
  ),
}))
vi.mock('./components/TodoFilters', () => ({ TodoFilters: () => null }))
vi.mock('./components/TodoList', () => ({
  TodoList: ({
    onToggle,
    onEdit,
    onDelete,
  }: {
    onToggle: (todo: typeof todoFixture) => void
    onEdit: (todo: typeof todoFixture) => void
    onDelete: (todo: typeof todoFixture) => void
  }) => (
    <div>
      <button type="button" onClick={() => onToggle(todoFixture)}>
        Toggle task
      </button>
      <button type="button" onClick={() => onEdit(todoFixture)}>
        Edit task
      </button>
      <button type="button" onClick={() => onDelete(todoFixture)}>
        Delete task
      </button>
    </div>
  ),
}))
vi.mock('./components/TodoEditor', () => ({
  TodoEditor: ({
    onClose,
    onSaved,
  }: {
    onClose: () => void
    onSaved: (notice: string) => void
  }) => (
    <div role="dialog" aria-label="Edit task">
      <button type="button" onClick={onClose}>
        Close editor
      </button>
      <button type="button" onClick={() => onSaved('Task saved.')}>
        Save task
      </button>
    </div>
  ),
}))
vi.mock('./components/DeleteTodoDialog', () => ({
  DeleteTodoDialog: ({
    onClose,
    onDeleted,
  }: {
    onClose: () => void
    onDeleted: () => void
  }) => (
    <div role="dialog" aria-label="Delete task?">
      <button type="button" onClick={onClose}>
        Close delete
      </button>
      <button type="button" onClick={onDeleted}>
        Confirm delete
      </button>
    </div>
  ),
}))
vi.mock('../../components/SuccessNotice', () => ({
  SuccessNotice: ({ message }: { message: string }) => <p>{message}</p>,
}))

it('displays a query failure and resets mutation errors before retrying', async () => {
  const user = userEvent.setup()
  const refetch = vi.fn().mockResolvedValue(undefined)
  const reset = vi.fn()
  vi.mocked(useTodosQuery).mockReturnValue({
    data: [],
    isPending: false,
    isFetching: false,
    isError: true,
    error: new Error('The server is unavailable.'),
    refetch,
  } as unknown as ReturnType<typeof useTodosQuery>)
  vi.mocked(useUpdateTodoMutation).mockReturnValue({
    error: null,
    reset,
    mutateAsync: vi.fn(),
  } as unknown as ReturnType<typeof useUpdateTodoMutation>)
  vi.mocked(useTodosBusy).mockReturnValue(false)
  vi.mocked(useNotice).mockReturnValue({ message: '', notify: vi.fn() })
  vi.mocked(useTodoFilters).mockReturnValue({
    filter: 'all',
    search: '',
    sort: 'newest',
    visible: [],
    setFilter: vi.fn(),
    setSearch: vi.fn(),
    setSort: vi.fn(),
  })
  render(<TodosPage />)
  expect(screen.getByTestId('alert')).toHaveTextContent(
    'The server is unavailable.',
  )
  await user.click(screen.getByRole('button', { name: 'Try again' }))
  await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1))
  expect(reset).toHaveBeenCalledTimes(1)
  expect(reset.mock.invocationCallOrder[0]).toBeLessThan(
    refetch.mock.invocationCallOrder[0],
  )
})

function mockPage(options?: {
  busy?: boolean
  mutateAsync?: ReturnType<typeof vi.fn>
}) {
  const notify = vi.fn()
  const mutateAsync =
    options?.mutateAsync ??
    vi.fn().mockResolvedValue({ ...todoFixture, completed: true })
  vi.mocked(useTodosQuery).mockReturnValue({
    data: [todoFixture],
    isPending: false,
    isFetching: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useTodosQuery>)
  vi.mocked(useUpdateTodoMutation).mockReturnValue({
    error: null,
    reset: vi.fn(),
    mutateAsync,
  } as unknown as ReturnType<typeof useUpdateTodoMutation>)
  vi.mocked(useTodosBusy).mockReturnValue(options?.busy ?? false)
  vi.mocked(useNotice).mockReturnValue({ message: '', notify })
  vi.mocked(useTodoFilters).mockReturnValue({
    filter: 'all',
    search: '',
    sort: 'newest',
    visible: [todoFixture],
    setFilter: vi.fn(),
    setSearch: vi.fn(),
    setSort: vi.fn(),
  })
  return { notify, mutateAsync }
}

it('toggles a task, edits it, and confirms deletion', async () => {
  const user = userEvent.setup()
  const { notify, mutateAsync } = mockPage()
  render(<TodosPage />)

  await user.click(screen.getByRole('button', { name: 'Toggle task' }))
  expect(mutateAsync).toHaveBeenCalledWith({
    id: todoFixture.id,
    input: { completed: true },
  })
  expect(notify).toHaveBeenCalledWith('Another task complete. Well done!')

  await user.click(screen.getByRole('button', { name: 'Create task' }))
  expect(screen.getByRole('dialog', { name: 'Edit task' })).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Save task' }))
  expect(notify).toHaveBeenCalledWith('Task saved.')
  expect(
    screen.queryByRole('dialog', { name: 'Edit task' }),
  ).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Delete task' }))
  await user.click(screen.getByRole('button', { name: 'Confirm delete' }))
  expect(notify).toHaveBeenCalledWith('Task deleted.')
  expect(
    screen.queryByRole('dialog', { name: 'Delete task?' }),
  ).not.toBeInTheDocument()
})

it('does not toggle while another task action is running', async () => {
  const user = userEvent.setup()
  const { mutateAsync } = mockPage({ busy: true })
  render(<TodosPage />)
  expect(screen.getByRole('button', { name: 'Create task' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Toggle task' }))
  expect(mutateAsync).not.toHaveBeenCalled()
})

it('keeps the page open when toggling fails and can close dialogs', async () => {
  const user = userEvent.setup()
  const { notify } = mockPage({
    mutateAsync: vi.fn().mockRejectedValue(new Error('nope')),
  })
  render(<TodosPage />)
  await user.click(screen.getByRole('button', { name: 'Toggle task' }))
  expect(notify).not.toHaveBeenCalled()

  await user.click(screen.getByRole('button', { name: 'Edit task' }))
  await user.click(screen.getByRole('button', { name: 'Close editor' }))
  expect(
    screen.queryByRole('dialog', { name: 'Edit task' }),
  ).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Delete task' }))
  await user.click(screen.getByRole('button', { name: 'Close delete' }))
  expect(
    screen.queryByRole('dialog', { name: 'Delete task?' }),
  ).not.toBeInTheDocument()
})

it('marks a completed task as active again', async () => {
  const user = userEvent.setup()
  const mutateAsync = vi
    .fn()
    .mockResolvedValue({ ...todoFixture, completed: false })
  const { notify } = mockPage({ mutateAsync })
  render(<TodosPage />)
  await user.click(screen.getByRole('button', { name: 'Toggle task' }))
  expect(notify).toHaveBeenCalledWith('Task marked as active.')
})
