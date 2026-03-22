import type {
  Cart,
  Category,
  OrderPayload,
  PaginatedResponse,
  Product,
  SessionPayload,
} from '../types'

type RequestOptions = RequestInit & {
  initData?: string
}

function extractErrorMessage(payload: unknown): string | null {
  if (typeof payload === 'string') {
    const normalized = payload.trim()
    return normalized || null
  }
  if (Array.isArray(payload)) {
    const messages = payload.map((item) => extractErrorMessage(item)).filter(Boolean)
    return messages.join('\n') || null
  }
  if (payload && typeof payload === 'object') {
    const messages = Object.values(payload)
      .map((item) => extractErrorMessage(item))
      .filter(Boolean)
    return messages.join('\n') || null
  }
  return null
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.initData) {
    headers.set('X-Telegram-Init-Data', options.initData)
  }
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(path, {
    ...options,
    headers,
  })
  if (!response.ok) {
    const payload = await response.text()
    let message = payload
    try {
      message = extractErrorMessage(JSON.parse(payload)) ?? payload
    } catch {
      message = payload
    }
    throw new Error(message || `Request failed with ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function fetchCategories(): Promise<Category[]> {
  return requestJson<Category[]>('/api/catalog/categories/')
}

export function fetchProducts(params: {
  categoryId?: number | null
  search?: string
  page?: number
}): Promise<PaginatedResponse<Product>> {
  const searchParams = new URLSearchParams()
  if (params.categoryId) {
    searchParams.set('category', String(params.categoryId))
  }
  if (params.search) {
    searchParams.set('search', params.search)
  }
  searchParams.set('page', String(params.page ?? 1))
  return requestJson<PaginatedResponse<Product>>(
    `/api/catalog/products/?${searchParams.toString()}`
  )
}

export function createSession(initData: string): Promise<SessionPayload> {
  return requestJson<SessionPayload>('/api/webapp/session/', {
    method: 'POST',
    body: JSON.stringify({ initData }),
  })
}

export function fetchCart(initData: string): Promise<Cart> {
  return requestJson<Cart>('/api/webapp/cart/', { initData })
}

export function addToCart(initData: string, productId: number): Promise<Cart> {
  return requestJson<Cart>('/api/webapp/cart/items/', {
    method: 'POST',
    initData,
    body: JSON.stringify({ product_id: productId, delta: 1 }),
  })
}

export function updateCartItem(
  initData: string,
  productId: number,
  quantity: number
): Promise<Cart> {
  return requestJson<Cart>(`/api/webapp/cart/items/${productId}/`, {
    method: 'PATCH',
    initData,
    body: JSON.stringify({ quantity }),
  })
}

export function removeCartItem(initData: string, productId: number): Promise<Cart> {
  return requestJson<Cart>(`/api/webapp/cart/items/${productId}/`, {
    method: 'DELETE',
    initData,
  })
}

export function clearCart(initData: string): Promise<Cart> {
  return requestJson<Cart>('/api/webapp/cart/clear/', {
    method: 'POST',
    initData,
  })
}

export function checkout(
  initData: string,
  payload: { full_name: string; address: string }
): Promise<OrderPayload> {
  return requestJson<OrderPayload>('/api/webapp/orders/checkout/', {
    method: 'POST',
    initData,
    body: JSON.stringify(payload),
  })
}
