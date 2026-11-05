import type { Todo } from '../types'

export interface TodoSummary {
  open: number
  completed: number
}

export function summarizeTodos(todos: Pick<Todo, 'completed'>[]): TodoSummary {
  const completed = todos.filter((todo) => todo.completed).length
  return { open: todos.length - completed, completed }
}

export function formatTodoSummary(summary: TodoSummary): string {
  return `${summary.open} open · ${summary.completed} completed`
}
