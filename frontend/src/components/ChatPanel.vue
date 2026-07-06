<script setup>
import { ref, nextTick } from 'vue'
import AppIcon from './AppIcon.vue'
import { sendChat } from '../api/client'
import { useChatSession } from '../composables/useChatSession'

const props = defineProps({
  propertyId: { type: [String, Number], required: true },
})

// Transcript + sending flag are shared session state (see composable) so
// the dashboard column and the focused Chat view show one conversation.
const { messages, isSending } = useChatSession()

const draft = ref('')
const scrollRegion = ref(null)

// Real questions verified against the actual ingested warranty document
// during testing (see tests/test_log.txt) — not placeholder copy.
const suggestedQuestions = [
  'Is a 1/8 inch crack in the drywall covered?',
  'Are plumbing leaks covered?',
  'What HVAC issues are covered?',
  'Is the roof covered under warranty?',
]

function askSuggested(question) {
  if (isSending.value) return
  draft.value = question
  send()
}

async function scrollToBottom() {
  await nextTick()
  if (scrollRegion.value) {
    scrollRegion.value.scrollTop = scrollRegion.value.scrollHeight
  }
}

async function ask(text) {
  isSending.value = true
  scrollToBottom()
  try {
    const result = await sendChat(props.propertyId, text)
    messages.value.push({ role: 'agent', text: result.answer, citations: result.citations || [] })
  } catch (err) {
    // Keep the failed question so a Retry can resend it without retyping.
    messages.value.push({
      role: 'agent',
      text: `The warranty agent couldn't answer: ${err.message}`,
      citations: [],
      error: true,
      retryText: text,
    })
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}

function send() {
  const text = draft.value.trim()
  if (!text || isSending.value) return
  messages.value.push({ role: 'client', text, citations: [] })
  draft.value = ''
  ask(text)
}

function retry(msg) {
  if (isSending.value) return
  ask(msg.retryText)
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-header">
      <h2 class="column-title">Warranty Assistant</h2>
      <span class="caption">Property #{{ propertyId }}</span>
    </div>

    <div class="message-stream" ref="scrollRegion" aria-live="polite">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="message-row"
        :class="msg.role"
      >
        <span class="avatar" aria-hidden="true">
          <AppIcon :name="msg.role === 'agent' ? 'bot' : 'user'" :size="13" />
        </span>
        <div class="bubble" :class="{ error: msg.error }">
          <p>{{ msg.text }}</p>
          <div class="citations" v-if="msg.citations.length">
            <span class="citation-chip" v-for="(c, ci) in msg.citations" :key="ci">{{ c }}</span>
          </div>
          <button v-if="msg.error" class="retry-btn" :disabled="isSending" @click="retry(msg)">
            <AppIcon name="refresh" :size="11" /> Retry
          </button>
        </div>
      </div>
      <div class="message-row agent" v-if="isSending">
        <span class="avatar" aria-hidden="true"><AppIcon name="bot" :size="13" /></span>
        <div class="bubble typing">Thinking…</div>
      </div>
    </div>

    <div class="suggested-row">
      <button
        v-for="(q, i) in suggestedQuestions"
        :key="i"
        class="suggested-chip"
        :disabled="isSending"
        @click="askSuggested(q)"
      >
        {{ q }}
      </button>
    </div>

    <form class="input-bar" @submit.prevent="send">
      <input
        v-model="draft"
        type="text"
        placeholder="Ask about warranty coverage…"
        :disabled="isSending"
        aria-label="Message"
      />
      <button type="submit" :disabled="isSending || !draft.trim()" aria-label="Send message">
        <AppIcon name="send" :size="15" />
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
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

/* Mirrors PropertyCard's .card-ribbon (same padding/background) so the
   three column titles align on one baseline. */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background-color: var(--color-bg-inset);
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
  background-color: var(--color-bg-inset);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bubble {
  background-color: var(--color-bg-inset);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 8px 12px;
}

.message-row.agent .bubble {
  background-color: color-mix(in srgb, var(--color-primary) 8%, var(--color-bg-inset));
}

.message-row.client .bubble {
  background-color: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.bubble.error {
  background-color: color-mix(in srgb, var(--color-danger) 8%, var(--color-bg-inset));
  border-color: color-mix(in srgb, var(--color-danger) 40%, var(--color-border));
}

.bubble p {
  margin: 0;
  font-size: var(--text-base);
  /* RAG answers arrive with real line breaks (two-step reasoning,
     numbered clauses) — keep them instead of collapsing to one blob. */
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.bubble.typing {
  color: var(--color-text-muted);
  font-style: italic;
}

.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  border: 1px solid var(--color-border);
  background-color: var(--color-bg-card);
  color: var(--color-text-main);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: var(--text-xs);
}

.citations {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.citation-chip {
  font-size: var(--text-xs);
  padding: 1px 6px;
  border-radius: 999px;
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

.suggested-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding: 0 12px 10px;
}

.suggested-chip {
  border: 1px solid var(--color-border);
  background-color: var(--color-bg-inset);
  color: var(--color-text-muted);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: var(--text-xs);
  white-space: nowrap;
}

.suggested-chip:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.suggested-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  background-color: var(--color-bg-inset);
  color: var(--color-text-main);
  font-size: var(--text-base);
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
