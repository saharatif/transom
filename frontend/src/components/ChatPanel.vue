<script setup>
import { ref, nextTick } from 'vue'
import { sendChat } from '../api/client'

const props = defineProps({
  propertyId: { type: [String, Number], required: true },
})

const messages = ref([
  {
    role: 'agent',
    text: "Ask me anything about this property's warranty coverage — I'll cite the exact clause.",
    citations: [],
  },
])
const draft = ref('')
const isSending = ref(false)
const scrollRegion = ref(null)

async function scrollToBottom() {
  await nextTick()
  if (scrollRegion.value) {
    scrollRegion.value.scrollTop = scrollRegion.value.scrollHeight
  }
}

async function send() {
  const text = draft.value.trim()
  if (!text || isSending.value) return

  messages.value.push({ role: 'client', text, citations: [] })
  draft.value = ''
  isSending.value = true
  scrollToBottom()

  try {
    const result = await sendChat(props.propertyId, text)
    messages.value.push({ role: 'agent', text: result.answer, citations: result.citations || [] })
  } catch (err) {
    messages.value.push({
      role: 'agent',
      text: 'Something went wrong reaching the warranty agent. Please try again.',
      citations: [],
    })
    console.error(err)
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-header">
      <span class="caption">Property #{{ propertyId }}</span>
      <h2>Warranty Assistant</h2>
    </div>

    <div class="message-stream" ref="scrollRegion">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="message-row"
        :class="msg.role"
      >
        <span class="avatar" aria-hidden="true">{{ msg.role === 'agent' ? '\u{1F916}' : '\u{1F9D1}' }}</span>
        <div class="bubble">
          <p>{{ msg.text }}</p>
          <div class="citations" v-if="msg.citations.length">
            <span class="citation-chip" v-for="(c, ci) in msg.citations" :key="ci">{{ c }}</span>
          </div>
        </div>
      </div>
      <div class="message-row agent" v-if="isSending">
        <span class="avatar" aria-hidden="true">&#129302;</span>
        <div class="bubble typing">Thinking…</div>
      </div>
    </div>

    <form class="input-bar" @submit.prevent="send">
      <input
        v-model="draft"
        type="text"
        placeholder="Input a message…"
        :disabled="isSending"
        aria-label="Message"
      />
      <button type="submit" :disabled="isSending || !draft.trim()" aria-label="Send message">
        &#10148;
      </button>
    </form>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
}

.chat-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.message-stream {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-row {
  display: flex;
  gap: 8px;
  max-width: 85%;
}

.message-row.client {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: var(--color-bg-main);
  border: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.bubble {
  background-color: var(--color-bg-main);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 8px 12px;
}

.message-row.agent .bubble {
  background-color: color-mix(in srgb, var(--color-primary) 10%, var(--color-bg-main));
}

.message-row.client .bubble {
  background-color: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.bubble p {
  margin: 0;
  font-size: 9.5pt;
}

.bubble.typing {
  color: var(--color-text-muted);
  font-style: italic;
}

.citations {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.citation-chip {
  font-size: 7.5pt;
  padding: 1px 6px;
  border-radius: 999px;
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

.input-bar {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--color-border);
}

.input-bar input {
  flex: 1;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 8px 14px;
  background-color: var(--color-bg-main);
  color: var(--color-text-main);
  font-size: 9.5pt;
}

.input-bar button {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background-color: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-bar button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
