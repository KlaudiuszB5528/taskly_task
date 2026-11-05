import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import { useTodoFilters } from './useTodoFilters'

it('filters, searches, and sorts the tasks it is given', () => {
  const completed = {
    ...todoFixture,
    id: 8,
    title: 'File notes',
    completed: true,
    created_at: '2026-09-01T12:00:00Z',
  }
  const { result } = renderHook(() => useTodoFilters([todoFixture, completed]))
  expect(result.current.filter).toBe('all')
  expect(result.current.search).toBe('')
  expect(result.current.sort).toBe('newest')
  expect(result.current.visible).toEqual([todoFixture, completed])

  act(() => result.current.setFilter('completed'))
  expect(result.current.visible).toEqual([completed])

  act(() => result.current.setSearch('missing'))
  expect(result.current.visible).toEqual([])

  act(() => {
    result.current.setSearch('')
    result.current.setFilter('all')
    result.current.setSort('priority')
  })
  expect(result.current.sort).toBe('priority')
  expect(result.current.visible.map((todo) => todo.id)).toEqual([8, 7])
})
