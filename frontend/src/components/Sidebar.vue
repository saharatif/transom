<script setup>
defineProps({
  activeTab: { type: String, default: 'properties' },
})
defineEmits(['select'])

const navItems = [
  { id: 'properties', label: 'Properties', icon: '\u{1F3E0}' },
  { id: 'clients', label: 'Clients', icon: '\u{1F465}' },
  { id: 'chat', label: 'Chat', icon: '\u{1F4AC}' },
  { id: 'upload', label: 'Upload', icon: '\u{2B06}\u{FE0F}' },
]
const settingsItem = { id: 'settings', label: 'Settings', icon: '\u{2699}\u{FE0F}' }
</script>

<template>
  <nav class="sidebar" aria-label="Primary navigation">
    <div class="sidebar-brand" aria-hidden="true">V</div>

    <ul class="sidebar-nav">
      <li v-for="item in navItems" :key="item.id">
        <button
          class="nav-btn"
          :class="{ active: activeTab === item.id }"
          :aria-label="item.label"
          :aria-current="activeTab === item.id ? 'page' : undefined"
          @click="$emit('select', item.id)"
        >
          <span class="nav-icon" aria-hidden="true">{{ item.icon }}</span>
        </button>
      </li>
    </ul>

    <button
      class="nav-btn settings-btn"
      :aria-label="settingsItem.label"
      @click="$emit('select', settingsItem.id)"
    >
      <span class="nav-icon" aria-hidden="true">{{ settingsItem.icon }}</span>
    </button>
  </nav>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 64px;
  min-width: 64px;
  height: 100%;
  background-color: var(--color-bg-sidebar);
  border-right: 1px solid var(--color-border);
  padding: 16px 0;
}

.sidebar-brand {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background-color: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  margin-bottom: 24px;
}

.sidebar-nav {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.nav-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 8px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.55;
  transition: opacity 0.2s ease, background-color 0.2s ease;
}

.nav-btn:hover {
  opacity: 0.85;
}

.nav-btn.active {
  opacity: 1;
  background-color: color-mix(in srgb, var(--color-primary) 15%, transparent);
}

.nav-icon {
  font-size: 18px;
}

.settings-btn {
  margin-top: auto;
}
</style>
