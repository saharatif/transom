<script setup>
import { ref, onMounted } from 'vue'

const isDarkMode = ref(false)

const toggleTheme = () => {
  isDarkMode.value = !isDarkMode.value
  document.documentElement.setAttribute('data-theme', isDarkMode.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light')
}

onMounted(() => {
  const savedTheme = localStorage.getItem('theme') || 'light'
  isDarkMode.value = savedTheme === 'dark'
  document.documentElement.setAttribute('data-theme', savedTheme)
})
</script>

<template>
  <button
    class="theme-toggle"
    role="switch"
    :aria-checked="isDarkMode"
    aria-label="Toggle dark mode"
    @click="toggleTheme"
  >
    <span class="track">
      <span class="thumb" :class="{ 'thumb-dark': isDarkMode }">
        {{ isDarkMode ? '\u{1F319}' : '\u{2600}\u{FE0F}' }}
      </span>
    </span>
  </button>
</template>

<style scoped>
.theme-toggle {
  border: none;
  background: transparent;
  padding: 0;
}

.track {
  display: flex;
  align-items: center;
  width: 56px;
  height: 28px;
  border-radius: 999px;
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  padding: 3px;
  box-shadow: var(--shadow-card);
}

.thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background-color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  transform: translateX(0);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.thumb-dark {
  transform: translateX(28px);
}
</style>
