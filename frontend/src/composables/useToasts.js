import { ref } from 'vue'

// Module-level state: one toast list shared by every component that
// imports this composable — no prop drilling or event bus needed.
const toasts = ref([])
let nextId = 1

export function useToasts() {
  function push(type, message, timeoutMs = 4500) {
    const id = nextId++
    toasts.value.push({ id, type, message })
    setTimeout(() => dismiss(id), timeoutMs)
    return id
  }

  function dismiss(id) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return {
    toasts,
    dismiss,
    success: (msg) => push('success', msg),
    error: (msg, timeoutMs = 7000) => push('error', msg, timeoutMs),
    info: (msg) => push('info', msg),
  }
}
