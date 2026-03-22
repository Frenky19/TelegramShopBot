import { startTransition, useDeferredValue, useEffect, useEffectEvent, useState } from 'react'

import { MAX_ADDRESS_LENGTH, MAX_FULL_NAME_LENGTH } from './constants'
import {
  addToCart,
  checkout,
  clearCart,
  createSession,
  fetchCategories,
  fetchProducts,
  removeCartItem,
  updateCartItem,
} from './lib/api'
import { applyTelegramTheme, getTelegramWebApp } from './lib/telegram'
import type { Cart, Category, Product, SessionPayload } from './types'

type ViewMode = 'catalog' | 'cart' | 'checkout'

const EMPTY_CART: Cart = { items: [], total_amount: '0.00' }

function findCategoryPath(
  categories: Category[],
  targetId: number,
): Category[] | null {
  for (const category of categories) {
    if (category.id === targetId) {
      return [category]
    }

    const nestedPath = findCategoryPath(category.children, targetId)
    if (nestedPath) {
      return [category, ...nestedPath]
    }
  }

  return null
}

function formatCurrency(value: string) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(Number(value))
}

function extractMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message
  }
  return 'Произошла ошибка.'
}

function validateCheckoutForm(form: { fullName: string; address: string }) {
  const fullName = form.fullName.trim().replace(/\s+/g, ' ')
  const address = form.address.trim()

  if (!fullName) {
    return 'Заполните ФИО получателя.'
  }
  if (fullName.length > MAX_FULL_NAME_LENGTH) {
    return `ФИО не должно превышать ${MAX_FULL_NAME_LENGTH} символов.`
  }
  if (!address) {
    return 'Заполните адрес доставки.'
  }
  if (address.length > MAX_ADDRESS_LENGTH) {
    return `Адрес не должен превышать ${MAX_ADDRESS_LENGTH} символов.`
  }

  return null
}

function App() {
  const webApp = getTelegramWebApp()
  const initData = webApp?.initData ?? import.meta.env.VITE_DEV_INIT_DATA ?? ''

  const [view, setView] = useState<ViewMode>('catalog')
  const [categories, setCategories] = useState<Category[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [session, setSession] = useState<SessionPayload | null>(null)
  const [cart, setCart] = useState<Cart>(EMPTY_CART)
  const [checkoutForm, setCheckoutForm] = useState({ fullName: '', address: '' })
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const deferredSearch = useDeferredValue(search)

  const bootstrap = useEffectEvent(async () => {
    applyTelegramTheme()
    try {
      const nextCategories = await fetchCategories()
      setCategories(nextCategories)
    } catch (bootstrapError) {
      setError(extractMessage(bootstrapError))
      return
    }

    if (!initData) {
      setNotice(
        'Откройте WebApp из Telegram, чтобы синхронизировать корзину и оформить заказ.'
      )
      return
    }

    try {
      const nextSession = await createSession(initData)
      setSession(nextSession)
      setCart(nextSession.cart)
    } catch (sessionError) {
      setError(extractMessage(sessionError))
    }
  })

  useEffect(() => {
    void bootstrap()
  }, [])

  const loadProducts = useEffectEvent(async () => {
    setCatalogLoading(true)
    try {
      const response = await fetchProducts({
        categoryId: selectedCategoryId,
        search: deferredSearch,
        page,
      })
      setProducts((previous) =>
        page === 1
          ? response.results
          : [...previous, ...response.results]
      )
      setHasNextPage(Boolean(response.next))
    } catch (catalogError) {
      setError(extractMessage(catalogError))
    } finally {
      setCatalogLoading(false)
    }
  })

  useEffect(() => {
    void loadProducts()
  }, [selectedCategoryId, deferredSearch, page])

  const handleBack = useEffectEvent(() => {
    startTransition(() => {
      setView((currentView) => (currentView === 'checkout' ? 'cart' : 'catalog'))
    })
  })

  useEffect(() => {
    if (!webApp) {
      return
    }
    if (view === 'catalog') {
      webApp.BackButton.hide()
      return
    }
    webApp.BackButton.show()
    webApp.BackButton.onClick(handleBack)
    return () => webApp.BackButton.offClick(handleBack)
  }, [view, webApp])

  async function submitCheckout() {
    if (!initData) {
      setError('Оформление заказа доступно только внутри Telegram.')
      return
    }

    const validationError = validateCheckoutForm(checkoutForm)
    if (validationError) {
      setError(validationError)
      return
    }

    const payload = {
      full_name: checkoutForm.fullName.trim().replace(/\s+/g, ' '),
      address: checkoutForm.address.trim(),
    }

    setBusy(true)
    setError(null)
    try {
      const order = await checkout(initData, payload)
      setCart(EMPTY_CART)
      setCheckoutForm({ fullName: '', address: '' })
      setNotice(
        `Заказ #${order.id} создан. Платежная заглушка: ${order.payment_stub_id}.`
      )
      startTransition(() => {
        setView('catalog')
      })
    } catch (checkoutError) {
      setError(extractMessage(checkoutError))
    } finally {
      setBusy(false)
    }
  }

  const handleMainButtonCheckout = useEffectEvent(() => {
    void submitCheckout()
  })

  useEffect(() => {
    if (!webApp) {
      return
    }
    if (view !== 'checkout') {
      webApp.MainButton.hide()
      return
    }
    webApp.MainButton.setText(busy ? 'Отправка...' : 'Подтвердить заказ')
    if (busy || !cart.items.length || Boolean(validateCheckoutForm(checkoutForm))) {
      webApp.MainButton.disable()
    } else {
      webApp.MainButton.enable()
    }
    webApp.MainButton.show()
    webApp.MainButton.onClick(handleMainButtonCheckout)
    return () => webApp.MainButton.offClick(handleMainButtonCheckout)
  }, [busy, cart.items.length, checkoutForm, view, webApp])

  async function mutateCart(operation: () => Promise<Cart>) {
    if (!initData) {
      setError('Корзина доступна только внутри Telegram.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const nextCart = await operation()
      setCart(nextCart)
    } catch (mutationError) {
      setError(extractMessage(mutationError))
    } finally {
      setBusy(false)
    }
  }

  function openCart() {
    startTransition(() => {
      setView('cart')
    })
  }

  function openCheckout() {
    startTransition(() => {
      setView('checkout')
    })
  }

  function resetCatalog(categoryId: number | null, nextSearch?: string) {
    setSelectedCategoryId(categoryId)
    if (typeof nextSearch === 'string') {
      setSearch(nextSearch)
    }
    setPage(1)
  }

  const activeCategoryPath =
    selectedCategoryId === null
      ? null
      : findCategoryPath(categories, selectedCategoryId)
  const selectedRootCategory = activeCategoryPath?.[0] ?? null
  const selectedSubcategoryId =
    activeCategoryPath && activeCategoryPath.length > 1
      ? activeCategoryPath[1].id
      : null
  const subcategoryOptions = selectedRootCategory?.children ?? []

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-copy">
          <h1>Выберите то, что вам нужно.</h1>
          <p className="hero-text">Каталог товаров с быстрым заказом.</p>
        </div>
        <button className="cart-pill" type="button" onClick={openCart}>
          Корзина
          <strong>{cart.items.reduce((sum, item) => sum + item.quantity, 0)}</strong>
        </button>
      </section>

      {(error || notice) && (
        <section className="status-stack">
          {error && <div className="banner banner-error">{error}</div>}
          {notice && <div className="banner banner-info">{notice}</div>}
        </section>
      )}

      <section className="toolbar">
        <label className="search-box">
          <span>Поиск</span>
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
            placeholder="Например, чехол или наушники"
          />
        </label>
        <div className="filter-groups">
          <div className="chips" aria-label="Категории">
            <button
              className={selectedCategoryId === null ? 'chip chip-active' : 'chip'}
              type="button"
              onClick={() => resetCatalog(null)}
            >
              Все
            </button>
            {categories.map((category) => (
              <button
                key={category.id}
                className={selectedRootCategory?.id === category.id ? 'chip chip-active' : 'chip'}
                type="button"
                onClick={() => resetCatalog(category.id)}
              >
                {category.title}
              </button>
            ))}
          </div>
          {subcategoryOptions.length > 0 && (
            <div className="chips chips-secondary" aria-label="Подкатегории">
              <button
                className={selectedSubcategoryId === null ? 'chip chip-active' : 'chip'}
                type="button"
                onClick={() => resetCatalog(selectedRootCategory?.id ?? null)}
              >
                Все в категории
              </button>
              {subcategoryOptions.map((subcategory) => (
                <button
                  key={subcategory.id}
                  className={selectedSubcategoryId === subcategory.id ? 'chip chip-active' : 'chip'}
                  type="button"
                  onClick={() => resetCatalog(subcategory.id)}
                >
                  {subcategory.title}
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      {view === 'catalog' && (
        <section className="catalog-grid">
          {products.map((product) => (
            <article key={product.id} className="product-card">
              <div className="product-image-wrap">
                {product.images[0]?.image ? (
                  <img
                    className="product-image"
                    src={product.images[0].image}
                    alt={product.title}
                  />
                ) : (
                  <div className="product-image product-fallback">
                    <span>{product.title.slice(0, 1)}</span>
                  </div>
                )}
              </div>
              <div className="product-body">
                <div className="product-meta">
                  <h2>{product.title}</h2>
                  <p>
                    {product.description ||
                      'Краткое описание появится после добавления товара в админке.'}
                  </p>
                </div>
                <div className="product-footer">
                  <strong>{formatCurrency(product.price)}</strong>
                  <button
                    type="button"
                    onClick={() => {
                      void mutateCart(() => addToCart(initData, product.id))
                    }}
                  >
                    В корзину
                  </button>
                </div>
              </div>
            </article>
          ))}
          {catalogLoading && <div className="loader-card">Загружаем каталог…</div>}
          {!catalogLoading && products.length === 0 && (
            <div className="loader-card">По текущему фильтру товары не найдены.</div>
          )}
          {hasNextPage && (
            <button
              className="load-more"
              type="button"
              onClick={() => setPage((currentPage) => currentPage + 1)}
            >
              Показать еще
            </button>
          )}
        </section>
      )}

      {view === 'cart' && (
        <section className="panel">
          <header className="panel-header">
            <div className="panel-copy">
              <p className="eyebrow">Корзина</p>
              <h2>
                {session?.customer.first_name
                  ? `${session.customer.first_name}, ваш заказ`
                  : 'Ваш заказ'}
              </h2>
            </div>
            <button
              className="ghost-button"
              type="button"
              onClick={() => void mutateCart(() => clearCart(initData))}
            >
              Очистить
            </button>
          </header>
          <div className="cart-list">
            {cart.items.length === 0 && <div className="empty-state">Корзина пока пуста.</div>}
            {cart.items.map((item) => (
              <article key={item.id} className="cart-row">
                <div>
                  <strong>{item.product.title}</strong>
                  <p>{formatCurrency(item.line_total)}</p>
                </div>
                <div className="cart-controls">
                  <button
                    type="button"
                    disabled={item.quantity <= 1}
                    onClick={() => {
                      if (item.quantity <= 1) {
                        return
                      }
                      void mutateCart(() =>
                        updateCartItem(
                          initData,
                          item.product.id,
                          item.quantity - 1
                        )
                      )
                    }}
                  >
                    −
                  </button>
                  <span>{item.quantity}</span>
                  <button
                    type="button"
                    onClick={() =>
                      void mutateCart(() =>
                        updateCartItem(
                          initData,
                          item.product.id,
                          item.quantity + 1
                        )
                      )
                    }
                  >
                    +
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      void mutateCart(() =>
                        removeCartItem(initData, item.product.id)
                      )
                    }
                  >
                    Удалить
                  </button>
                </div>
              </article>
            ))}
          </div>
          <footer className="panel-footer">
            <div>
              <p>Итого</p>
              <strong>{formatCurrency(cart.total_amount)}</strong>
            </div>
            <button type="button" onClick={openCheckout} disabled={!cart.items.length}>
              Перейти к оформлению
            </button>
          </footer>
        </section>
      )}

      {view === 'checkout' && (
        <section className="panel">
          <header className="panel-header">
            <div>
              <p className="eyebrow">Checkout</p>
              <h2>Данные для доставки</h2>
            </div>
          </header>
          <div className="form-grid">
            <label className="field">
              <span>ФИО</span>
              <input
                value={checkoutForm.fullName}
                onChange={(event) =>
                  setCheckoutForm((current) => ({ ...current, fullName: event.target.value }))
                }
                placeholder="Иванов Иван Иванович"
              />
            </label>
            <label className="field field-wide">
              <span>Адрес</span>
              <textarea
                value={checkoutForm.address}
                onChange={(event) =>
                  setCheckoutForm((current) => ({ ...current, address: event.target.value }))
                }
                placeholder="Город, улица, дом, квартира, комментарий для курьера"
              />
            </label>
          </div>
          <div className="checkout-summary">
            <p>Телефон будет взят из Telegram-профиля.</p>
            <strong>{formatCurrency(cart.total_amount)}</strong>
          </div>
          {!webApp && (
            <button
              className="checkout-fallback"
              type="button"
              onClick={() => void submitCheckout()}
              disabled={busy}
            >
              Подтвердить заказ
            </button>
          )}
        </section>
      )}
    </main>
  )
}

export default App
