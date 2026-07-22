import { ref, computed } from 'vue'

// 主题模式：light / dark / system
const STORAGE_KEY = 'ma_theme'

export const themeMode = ref(
  (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY)) || 'system'
)

const mq =
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : { matches: false, addEventListener() {} }

export const systemDark = ref(mq.matches)
if (mq.addEventListener) {
  mq.addEventListener('change', (e) => {
    systemDark.value = e.matches
    applyTheme()
  })
}

export const isDark = computed(
  () => themeMode.value === 'dark' || (themeMode.value === 'system' && systemDark.value)
)

export function applyTheme() {
  const dark = isDark.value
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', dark)
    document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
  }
  if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, themeMode.value)
}

export function setTheme(mode) {
  themeMode.value = mode
  applyTheme()
}

applyTheme()
