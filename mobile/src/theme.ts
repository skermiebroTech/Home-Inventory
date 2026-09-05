/** The colours and the spacing. One quiet neutral ramp and one accent. */

import { useColorScheme } from 'react-native'

export interface Theme {
  dark: boolean
  bg: string
  card: string
  border: string
  text: string
  muted: string
  accent: string
  accentText: string
  danger: string
  warn: string
  ok: string
}

const LIGHT: Theme = {
  dark: false,
  bg: '#f8fafc',
  card: '#ffffff',
  border: '#e2e8f0',
  text: '#0f172a',
  muted: '#64748b',
  accent: '#2563eb',
  accentText: '#ffffff',
  danger: '#dc2626',
  warn: '#d97706',
  ok: '#059669',
}

const DARK: Theme = {
  dark: true,
  bg: '#020617',
  card: '#0f172a',
  border: '#1e293b',
  text: '#f1f5f9',
  muted: '#94a3b8',
  accent: '#3b82f6',
  accentText: '#ffffff',
  danger: '#f87171',
  warn: '#fbbf24',
  ok: '#34d399',
}

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? DARK : LIGHT
}

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 }
export const radius = { sm: 8, md: 12, lg: 16 }
