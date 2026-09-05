/** Short messages that confirm an action or report a failure. */

import { create } from 'zustand'

export type ToastTone = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  tone: ToastTone
  message: string
}

interface ToastState {
  toasts: Toast[]
  push: (message: string, tone?: ToastTone) => void
  dismiss: (id: number) => void
}

let counter = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, tone = 'info') => {
    const id = ++counter
    set((state) => ({ toasts: [...state.toasts, { id, tone, message }] }))
    window.setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) }))
    }, 4500)
  },
  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
}))

/** Report a failure with the message that the server sent. */
export function toastError(error: unknown, fallback = 'That did not work.'): void {
  const message = error instanceof Error ? error.message : fallback
  useToastStore.getState().push(message, 'error')
}

export function toastOk(message: string): void {
  useToastStore.getState().push(message, 'success')
}
