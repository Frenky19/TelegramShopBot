export interface Category {
  id: number
  title: string
  parent: number | null
  children: Category[]
}

export interface ProductImage {
  id: number
  image: string
  alt_text: string
  sort_order: number
}

export interface Product {
  id: number
  category: number
  title: string
  slug: string
  description: string
  price: string
  images: ProductImage[]
}

export interface CartItem {
  id: number
  product: Product
  quantity: number
  line_total: string
}

export interface Cart {
  items: CartItem[]
  total_amount: string
}

export interface Customer {
  id: number
  telegram_id: number
  username: string
  first_name: string
  last_name: string
  phone: string
  language_code: string
  is_bot_admin: boolean
}

export interface BotSettings {
  admin_chat_id: number | null
  catalog_webapp_url: string
  help_text: string
  subscription_message: string
  required_channels: Array<{
    id: number
    title: string
    chat_id: number | null
    username: string
    subscription_url: string
  }>
}

export interface SessionPayload {
  customer: Customer
  cart: Cart
  settings: BotSettings
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface OrderPayload {
  id: number
  status: string
  status_display: string
  full_name: string
  phone: string
  address: string
  total_amount: string
  payment_stub_id: string
}
