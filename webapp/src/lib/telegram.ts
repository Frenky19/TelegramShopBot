type ThemeMode = 'dark' | 'light'

let subscribedWebApp: TelegramWebApp | undefined
let themeChangeHandler: (() => void) | undefined

export function getTelegramWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp
}

function normalizeHexColor(value?: string) {
  if (!value) {
    return null
  }

  const color = value.trim()
  if (!color.startsWith('#')) {
    return null
  }

  const hex = color.slice(1)
  if (hex.length === 3) {
    return `#${hex
      .split('')
      .map((char) => char + char)
      .join('')}`
  }
  if (hex.length === 6) {
    return color.toLowerCase()
  }

  return null
}

function calculateLuminance(value?: string) {
  const normalized = normalizeHexColor(value)
  if (!normalized) {
    return null
  }

  const red = Number.parseInt(normalized.slice(1, 3), 16) / 255
  const green = Number.parseInt(normalized.slice(3, 5), 16) / 255
  const blue = Number.parseInt(normalized.slice(5, 7), 16) / 255

  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

function resolveThemeMode(webApp: TelegramWebApp): ThemeMode {
  if (webApp.colorScheme === 'dark' || webApp.colorScheme === 'light') {
    return webApp.colorScheme
  }

  const backgroundLuminance = calculateLuminance(webApp.themeParams.bg_color)
  if (backgroundLuminance !== null) {
    return backgroundLuminance < 0.5 ? 'dark' : 'light'
  }

  const textLuminance = calculateLuminance(webApp.themeParams.text_color)
  if (textLuminance !== null) {
    return textLuminance > 0.65 ? 'dark' : 'light'
  }

  return 'light'
}

function syncTelegramTheme(webApp: TelegramWebApp) {
  const themeMode = resolveThemeMode(webApp)
  const theme = webApp.themeParams
  const root = document.documentElement
  const mapping: Record<string, string | undefined> = {
    '--tg-bg': theme.bg_color,
    '--tg-surface': theme.secondary_bg_color,
    '--tg-text': theme.text_color,
    '--tg-muted': theme.hint_color,
    '--tg-link': theme.link_color,
    '--tg-button': theme.button_color,
    '--tg-button-text': theme.button_text_color,
    '--tg-accent': theme.accent_text_color,
  }

  root.dataset.theme = themeMode
  root.style.colorScheme = themeMode

  Object.entries(mapping).forEach(([key, value]) => {
    if (value) {
      root.style.setProperty(key, value)
      return
    }
    root.style.removeProperty(key)
  })
}

export function applyTelegramTheme(): TelegramWebApp | undefined {
  const webApp = getTelegramWebApp()
  if (!webApp) {
    return undefined
  }

  webApp.ready()
  webApp.expand()
  syncTelegramTheme(webApp)

  if (subscribedWebApp !== webApp && themeChangeHandler) {
    subscribedWebApp?.offEvent?.('themeChanged', themeChangeHandler)
  }

  if (subscribedWebApp !== webApp || !themeChangeHandler) {
    themeChangeHandler = () => {
      syncTelegramTheme(webApp)
    }
    subscribedWebApp = webApp
    webApp.onEvent?.('themeChanged', themeChangeHandler)
  }

  return webApp
}
