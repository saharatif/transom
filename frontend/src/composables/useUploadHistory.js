import { computed, ref } from 'vue'

// Module-level state: the dashboard column and the focused Upload view
// each mount their own FileUpload instance — sharing the queue here keeps
// one session-wide history regardless of which view an upload started in.
// The backend doesn't store an ingestion-event log table, only the
// extracted results themselves (see backend/db/schema.sql), so history is
// client-side per session.
const history = ref([])

export function useUploadHistory() {
  const activeItems = computed(() => history.value.filter((h) => h.status === 'processing'))

  function startItem(fileName, docTypeLabel) {
    history.value.unshift({
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      fileName,
      docTypeLabel,
      status: 'processing',
    })
    // Return the reactive proxy from the array (not the plain literal)
    // so mutating .status later triggers reactivity.
    return history.value[0]
  }

  function clear() {
    history.value = []
  }

  return { history, activeItems, startItem, clear }
}
