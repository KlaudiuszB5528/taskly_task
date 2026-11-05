import { afterEach, expect, it, vi } from 'vitest'
import { request } from './http'

afterEach(() => vi.unstubAllGlobals())

function jsonResponse(status: number, body: unknown, ok = status < 400) {
  return {
    ok,
    status,
    json: () => Promise.resolve(body),
  }
}

it('returns parsed JSON and prefixes the API path', async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { id: 1 }))
  vi.stubGlobal('fetch', fetchMock)
  await expect(request<{ id: number }>('/todos')).resolves.toEqual({ id: 1 })
  expect(fetchMock).toHaveBeenCalledWith('/api/todos', {
    headers: { 'Content-Type': 'application/json' },
  })
})

it('returns undefined for an empty success response', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: () => {
        throw new Error('204 should not be parsed')
      },
    }),
  )
  await expect(
    request<void>('/todos/7', { method: 'DELETE' }),
  ).resolves.toBeUndefined()
})

it('preserves caller headers while forcing JSON content type', async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }))
  vi.stubGlobal('fetch', fetchMock)
  await request('/todos', {
    method: 'POST',
    headers: { 'X-Request-Id': 'abc' },
    body: '{}',
  })
  expect(fetchMock).toHaveBeenCalledWith('/api/todos', {
    method: 'POST',
    body: '{}',
    headers: { 'Content-Type': 'application/json', 'X-Request-Id': 'abc' },
  })
})

it('maps validation failures to a field guidance message', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(jsonResponse(422, { detail: [] }, false)),
  )
  await expect(request('/todos', { method: 'POST' })).rejects.toThrow(
    'Check the task details: title up to 120 characters, description up to 2000 characters, and a valid due date.',
  )
})

it('uses a string error detail from the server', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        jsonResponse(404, { detail: 'Task not found.' }, false),
      ),
  )
  await expect(request('/todos/7')).rejects.toThrow('Task not found.')
})

it('uses a generic message when the error detail is not a string', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        jsonResponse(400, { detail: [{ msg: 'bad' }] }, false),
      ),
  )
  await expect(request('/todos')).rejects.toThrow(
    'The operation failed. Please try again.',
  )
})

it('uses a generic message when the error body is not JSON', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error('not json')),
    }),
  )
  await expect(request('/todos')).rejects.toThrow(
    'The operation failed. Please try again.',
  )
})

it('maps a network failure to a connection error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
  await expect(request('/todos')).rejects.toThrow(
    'Cannot connect to the server. Please try again.',
  )
})

it('rethrows an aborted request', async () => {
  const controller = new AbortController()
  controller.abort()
  const abortError = new DOMException(
    'The operation was aborted.',
    'AbortError',
  )
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError))
  await expect(request('/todos', { signal: controller.signal })).rejects.toBe(
    abortError,
  )
})
