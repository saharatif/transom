<script setup>
import { ref, onMounted } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import FileUpload from './components/FileUpload.vue'
import PropertyCard from './components/PropertyCard.vue'
import RenovationTable from './components/RenovationTable.vue'
import ChatPanel from './components/ChatPanel.vue'
import { getProperty } from './api/client'

const activeTab = ref('properties')
const propertyId = ref(1)
const propertyData = ref(null)
const loadError = ref('')

async function refreshProperty() {
  try {
    propertyData.value = await getProperty(propertyId.value)
    loadError.value = ''
  } catch (err) {
    loadError.value = 'Could not reach the Property Intelligence API. Is the backend running on :8000?'
    console.error(err)
  }
}

function onIngested() {
  // Any successful upload can change property fields (sqft, condition,
  // renovation estimate, etc.) — refetch the combined view.
  refreshProperty()
}

onMounted(refreshProperty)
</script>

<template>
  <div class="dashboard-wrapper">
    <Sidebar :active-tab="activeTab" @select="activeTab = $event" />

    <div class="dashboard-main">
      <header class="dashboard-header">
        <h1>Property Dashboard</h1>
        <ThemeToggle />
      </header>

      <p class="caption error-banner" v-if="loadError">{{ loadError }}</p>

      <div class="dashboard-columns">
        <section class="column" aria-label="Upload">
          <FileUpload :property-id="propertyId" @ingested="onIngested" />
        </section>

        <section class="column" aria-label="Property details">
          <PropertyCard :data="propertyData" />
          <RenovationTable :renovations="propertyData?.renovations || []" />
        </section>

        <section class="column chat-column" aria-label="Chat">
          <ChatPanel :property-id="propertyId" />
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-wrapper {
  display: flex;
  height: 100vh;
  background-color: var(--color-bg-main);
  color: var(--color-text-main);
}

.dashboard-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 24px 32px;
  gap: 20px;
  overflow: hidden;
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.error-banner {
  color: #d1242f;
}

.dashboard-columns {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1.1fr 1fr;
  gap: 20px;
  min-height: 0;
}

.column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.chat-column {
  min-height: 0;
}

@media (max-width: 960px) {
  .dashboard-columns {
    grid-template-columns: 1fr;
  }
}
</style>
