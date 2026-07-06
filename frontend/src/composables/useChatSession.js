import { ref } from 'vue'

// Module-level state: the dashboard column and the focused Chat view each
// mount their own ChatPanel — sharing the transcript here means switching
// views continues the same conversation instead of starting a blank one.
const GREETING = {
  role: 'agent',
  text: "Ask me anything about this property's warranty coverage — I'll cite the exact clause.",
  citations: [],
}

const messages = ref([{ ...GREETING }])
const isSending = ref(false)

export function useChatSession() {
  function reset() {
    messages.value = [{ ...GREETING }]
  }

  return { messages, isSending, reset }
}
