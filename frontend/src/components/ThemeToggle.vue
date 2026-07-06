<script setup>
import { ref, onMounted } from 'vue'
import AppIcon from './AppIcon.vue'

const isDarkMode = ref(false)

const toggleTheme = () => {
  isDarkMode.value = !isDarkMode.value
  document.documentElement.setAttribute('data-theme', isDarkMode.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light')
}

onMounted(() => {
  // index.html's inline script already applies the saved/default theme
  // before Vue mounts (avoids a flash of the wrong theme) — this just
  // syncs the toggle's own visual state to match.
  const savedTheme = document.documentElement.getAttribute('data-theme') || 'dark'
  isDarkMode.value = savedTheme === 'dark'
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
        <AppIcon :name="isDarkMode ? 'moon' : 'sun'" :size="12" />
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
  color: #fff;
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
