import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useNotice } from './useNotice'

afterEach(() => vi.useRealTimers())

it('starts without a notice and exposes a notification callback', () => {
  const { result } = renderHook(() => useNotice())
  expect(result.current.message).toBe('')
  expect(result.current.notify).toEqual(expect.any(Function))
})

it('shows a notice and clears it after four seconds', () => {
  vi.useFakeTimers()
  const { result } = renderHook(() => useNotice())
  act(() => result.current.notify('Task saved.'))
  expect(result.current.message).toBe('Task saved.')
  act(() => vi.advanceTimersByTime(3999))
  expect(result.current.message).toBe('Task saved.')
  act(() => vi.advanceTimersByTime(1))
  expect(result.current.message).toBe('')
})

it('cancels the previous timer when a new notice replaces it', () => {
  vi.useFakeTimers()
  const { result } = renderHook(() => useNotice())
  act(() => result.current.notify('First'))
  act(() => vi.advanceTimersByTime(2000))
  act(() => result.current.notify('Second'))
  act(() => vi.advanceTimersByTime(2000))
  expect(result.current.message).toBe('Second')
  act(() => vi.advanceTimersByTime(2000))
  expect(result.current.message).toBe('')
})
