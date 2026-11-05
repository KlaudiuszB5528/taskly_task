import { describe, expect, it } from 'vitest'
import type { Todo, TodoInput } from '../types'
import { formatDate, isOverdue, selectTodos, validateTodo } from './todos'

const base: Todo = {
  id: 1,
  title: 'Sprint plan',
  description: '',
  priority: 'medium',
  completed: false,
  due_date: null,
  created_at: '2026-10-01T12:00:00Z',
  updated_at: '2026-10-01T12:00:00Z',
}

describe('selectTodos', () => {
  it('combines status with a case-insensitive search in the description', () => {
    const matching = { ...base, description: 'Discuss the API' }
    const todos = [
      matching,
      { ...matching, id: 2, completed: true },
      { ...base, id: 3 },
    ]
    expect(selectTodos(todos, 'active', ' api ', 'newest')).toEqual([matching])
  })

  it('sorts by priority without changing the source array', () => {
    const high: Todo = { ...base, id: 2, priority: 'high' }
    const todos = [base, high]
    expect(selectTodos(todos, 'all', '', 'priority')).toEqual([high, base])
    expect(todos).toEqual([base, high])
  })

  it('returns completed tasks and orders the newest created date first', () => {
    const older = { ...base, created_at: '2026-01-01T00:00:00Z' }
    const newer = { ...base, id: 2, created_at: '2026-06-01T00:00:00Z' }
    const done = { ...newer, id: 3, completed: true }
    expect(selectTodos([older, done], 'completed', '', 'newest')).toEqual([
      done,
    ])
    expect(selectTodos([older, newer], 'all', '', 'newest')).toEqual([
      newer,
      older,
    ])
  })

  it('sorts by due date and leaves undated tasks last', () => {
    const later = { ...base, id: 2, due_date: '2026-12-01' }
    const sooner = { ...base, id: 3, due_date: '2026-01-01' }
    const same = { ...base, id: 1, due_date: '2026-01-01' }
    const undated = { ...base, id: 4, due_date: null }
    expect(
      selectTodos([later, undated, same, sooner], 'all', '', 'due'),
    ).toEqual([sooner, same, later, undated])
  })
})

describe('validateTodo', () => {
  const input: TodoInput = {
    title: 'Sprint plan',
    description: '',
    priority: 'medium',
    due_date: null,
    completed: false,
  }

  it('accepts a title and an empty optional description', () => {
    expect(validateTodo(input)).toEqual({})
  })

  it('rejects a blank title, an overlong field, and an impossible date', () => {
    expect(validateTodo({ ...input, title: '   ' })).toEqual({
      title: 'Enter a task title.',
    })
    expect(validateTodo({ ...input, title: 'x'.repeat(121) }).title).toMatch(
      /120/,
    )
    expect(
      validateTodo({ ...input, description: 'x'.repeat(2001) }).description,
    ).toMatch(/2000/)
    expect(validateTodo({ ...input, due_date: '2026-02-30' })).toEqual({
      due_date: 'Enter a valid date.',
    })
  })
})

describe('isOverdue', () => {
  it('is true only for an incomplete task whose due date is before today', () => {
    expect(isOverdue({ ...base, due_date: '2000-01-01' })).toBe(true)
    expect(isOverdue({ ...base, due_date: '2999-01-01' })).toBe(false)
    expect(
      isOverdue({ ...base, due_date: '2000-01-01', completed: true }),
    ).toBe(false)
    expect(isOverdue({ ...base, due_date: null })).toBe(false)
  })
})

describe('formatDate', () => {
  it('formats a calendar date in day month year order', () => {
    expect(formatDate('2026-10-15')).toBe('15 Oct 2026')
  })
})
