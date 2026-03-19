export function getTelegramWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp
}

export function applyTelegramTheme(): TelegramWebApp | undefined {
  const webApp = getTelegramWebApp()
  if (!webApp) {
    return undefined
  }

  webApp.ready()
  webApp.expand()

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

  Object.entries(mapping).forEach(([key, value]) => {
    if (value) {
      root.style.setProperty(key, value)
    }
  })

  return webApp
}
