<script setup>
import AppIcon from './AppIcon.vue'
import BrandLogo from './BrandLogo.vue'

defineProps({
  activeTab: { type: String, default: 'dashboard' },
})
defineEmits(['select'])

// Only nav items that map to something real in the app — no Portfolio /
// Clients / Reports placeholders for pages that don't exist yet.
const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: 'home' },
  { id: 'upload', label: 'Upload', icon: 'upload' },
  { id: 'chat', label: 'Chat', icon: 'chat' },
]
const settingsItem = { id: 'settings', label: 'Settings', icon: 'settings' }
</script>

<template>
  <nav class="sidebar" aria-label="Primary navigation">
    <div class="sidebar-brand">
      <BrandLogo :size="32" :show-text="false" />
      <span class="brand-name">Transom</span>
    </div>

    <ul class="sidebar-nav">
      <li v-for="item in navItems" :key="item.id">
        <button
          class="nav-btn"
          :class="{ active: activeTab === item.id }"
          :aria-current="activeTab === item.id ? 'page' : undefined"
          @click="$emit('select', item.id)"
        >
          <span class="nav-icon"><AppIcon :name="item.icon" :size="16" /></span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </li>
    </ul>

    <button
      class="nav-btn settings-btn"
      :class="{ active: activeTab === settingsItem.id }"
      :aria-current="activeTab === settingsItem.id ? 'page' : undefined"
      @click="$emit('select', settingsItem.id)"
    >
      <span class="nav-icon"><AppIcon :name="settingsItem.icon" :size="16" /></span>
      <span class="nav-label">{{ settingsItem.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: 200px;
  min-width: 200px;
  height: 100%;
  background-color: var(--color-bg-sidebar);
  border-right: 1px solid var(--color-border);
  padding: 20px 12px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px;
  margin-bottom: 28px;
}

.brand-name {
  font-weight: 700;
  font-size: var(--text-md);
  letter-spacing: 0.02em;
  color: var(--color-text-main);
}

.sidebar-nav {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.nav-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border: none;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--text-base);
  text-align: left;
  transition: opacity 0.2s ease, background-color 0.2s ease, color 0.2s ease;
}

.nav-btn:hover {
  background-color: color-mix(in srgb, var(--color-primary) 8%, transparent);
  color: var(--color-text-main);
}

.nav-btn.active {
  color: var(--color-primary);
  background-color: color-mix(in srgb, var(--color-primary) 15%, transparent);
  font-weight: 600;
}

.nav-icon {
  display: flex;
  width: 20px;
  justify-content: center;
  flex-shrink: 0;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.settings-btn {
  margin-top: auto;
}
</style>
