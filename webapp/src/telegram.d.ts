interface TelegramThemeParams {
  bg_color?: string
  secondary_bg_color?: string
  text_color?: string
  hint_color?: string
  link_color?: string
  button_color?: string
  button_text_color?: string
  accent_text_color?: string
}

interface TelegramButton {
  show(): void
  hide(): void
  enable(): void
  disable(): void
  setText(text: string): void
  onClick(callback: () => void): void
  offClick(callback: () => void): void
}

interface TelegramBackButton {
  show(): void
  hide(): void
  onClick(callback: () => void): void
  offClick(callback: () => void): void
}

interface TelegramWebApp {
  initData: string
  colorScheme?: 'light' | 'dark'
  themeParams: TelegramThemeParams
  ready(): void
  expand(): void
  onEvent?(eventType: 'themeChanged', callback: () => void): void
  offEvent?(eventType: 'themeChanged', callback: () => void): void
  MainButton: TelegramButton
  BackButton: TelegramBackButton
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp
  }
}
