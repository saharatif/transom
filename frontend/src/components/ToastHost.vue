<script setup>
import AppIcon from './AppIcon.vue'
import { useToasts } from '../composables/useToasts'

const { toasts, dismiss } = useToasts()

const ICONS = { success: 'check', error: 'alert', info: 'clock' }
</script>

<template>
  <!-- aria-live so screen readers announce upload results/errors -->
  <div class="toast-host" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">
        <span class="toast-icon"><AppIcon :name="ICONS[t.type]" :size="15" /></span>
        <span class="toast-message">{{ t.message }}</span>
        <button class="toast-close" aria-label="Dismiss notification" @click="dismiss(t.id)">
          &times;
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 100;
  max-width: 360px;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-control);
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-card);
  font-size: var(--text-sm);
  color: var(--color-text-main);
}

.toast-icon {
  display: flex;
  margin-top: 1px;
  flex-shrink: 0;
}

.toast.success .toast-icon { color: var(--color-success); }
.toast.error .toast-icon { color: var(--color-danger); }
.toast.info .toast-icon { color: var(--color-primary); }

.toast.success { border-left: 3px solid var(--color-success); }
.toast.error { border-left: 3px solid var(--color-danger); }
.toast.info { border-left: 3px solid var(--color-primary); }

.toast-message {
  flex: 1;
  overflow-wrap: anywhere;
}

.toast-close {
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 16px;
  line-height: 1;
  padding: 0 2px;
  flex-shrink: 0;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
