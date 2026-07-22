<script setup>
import { computed, ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import BrandLogo from './components/BrandLogo.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import FileUpload from './components/FileUpload.vue'
import PropertyCard from './components/PropertyCard.vue'
import RenovationTable from './components/RenovationTable.vue'
import ChatPanel from './components/ChatPanel.vue'
import ToastHost from './components/ToastHost.vue'
import AppIcon from './components/AppIcon.vue'
import { getProperty, resetDatabase } from './api/client'
import { useToasts } from './composables/useToasts'
import { useUploadHistory } from './composables/useUploadHistory'
import { useChatSession } from './composables/useChatSession'

const toasts = useToasts()
const uploadHistory = useUploadHistory()
const chatSession = useChatSession()

// Sidebar navigation: dashboard = full 3-column workspace; upload/chat =
// focused single-panel views of the same components (state like upload
// history lives in those components' own refs, but v-show keeps them
// mounted so nothing resets when switching views); settings = theme +
// connection info.
const activeTab = ref('dashboard')

const propertyId = ref(1)
const propertyData = ref(null)
// 'idle' | 'loading' | 'ready' | 'notfound' | 'error' — a 404 (no such
// property yet) needs different messaging than the backend being
// unreachable; 'idle' is the fresh-session state before any activity.
const loadState = ref('idle')
const loadError = ref('')
const isRefreshing = ref(false)

// Session-gated display (user request): every page load starts with an
// empty dashboard, even if the database still holds data from earlier
// sessions — property data only appears after an action taken in THIS
// session (a successful upload, or explicitly jumping to a property ID).
// Nothing is deleted on refresh; the DB (and MCP tools) keep everything.
// The trash button is the way to actually clear stored data.
//
// Gating is per document type: uploading only photos must not reveal
// stored renovation priorities (inspection-form data) or bed/bath/value
// details (blueprint/inspection data) left over from earlier sessions —
// each panel unlocks with the doc type that feeds it. An explicit
// property-ID search is the exception: looking a property up means
// "show me everything stored for it."
const sessionActive = ref(false)
const sessionDocTypes = ref(new Set())
// property_images row ids created by THIS session's photo uploads —
// photos accumulate per property in the DB across sessions, so the photo
// tiles filter to these (see visibleImages) unless the property was
// explicitly looked up.
const sessionImageIds = ref(new Set())
const explicitLookup = ref(false)

// Blueprint data (size/rooms) and inspection data (builder/year/address,
// and the valuation computed from year_built) unlock separately — a
// blueprint-only session must not surface the price or builder stored
// by an earlier session's inspection form.
const showSpecs = computed(() =>
  explicitLookup.value || sessionDocTypes.value.has('blueprint') || sessionDocTypes.value.has('inspection'))
const showValuation = computed(() =>
  explicitLookup.value || sessionDocTypes.value.has('inspection'))
const visibleRenovations = computed(() =>
  explicitLookup.value || sessionDocTypes.value.has('inspection')
    ? propertyData.value?.renovations || []
    : [])
const visibleImages = computed(() => {
  const all = propertyData.value?.images || []
  return explicitLookup.value ? all : all.filter((img) => sessionImageIds.value.has(img.id))
})

const searchInput = ref('')

function onSearchSubmit() {
  const id = parseInt(searchInput.value, 10)
  if (!Number.isNaN(id) && id > 0) {
    propertyId.value = id
    searchInput.value = ''
    // Explicitly asking for a property counts as session activity and
    // unlocks the full stored view of it.
    sessionActive.value = true
    explicitLookup.value = true
    refreshProperty()
  } else if (searchInput.value.trim()) {
    toasts.info('Property IDs are positive numbers — try "1".')
  }
}

async function refreshProperty() {
  if (!sessionActive.value) return
  isRefreshing.value = true
  if (!propertyData.value) loadState.value = 'loading'
  try {
    propertyData.value = await getProperty(propertyId.value)
    loadState.value = 'ready'
    loadError.value = ''
  } catch (err) {
    propertyData.value = null
    if (err.status === 404) {
      loadState.value = 'notfound'
      loadError.value = ''
    } else {
      loadState.value = 'error'
      loadError.value = err.message
    }
  } finally {
    isRefreshing.value = false
  }
}

function onManualRefresh() {
  if (!sessionActive.value) {
    toasts.info('Fresh session — upload documents (or search a property ID) to load data.')
    return
  }
  refreshProperty()
}

function onIngested({ docType, result }) {
  // Any successful upload can change property fields (sqft, condition,
  // renovation estimate, etc.) — refetch the combined view, and unlock
  // the panel(s) this document type feeds.
  sessionActive.value = true
  sessionDocTypes.value = new Set([...sessionDocTypes.value, docType])
  if (docType === 'photo' && result?.image_id != null) {
    sessionImageIds.value = new Set([...sessionImageIds.value, result.image_id])
  }
  refreshProperty()
}

// Two-step confirm for the destructive reset: first click arms the
// button, second click (within 4s) actually wipes the ingested data.
const resetArmed = ref(false)
const isResetting = ref(false)
let disarmTimer

async function onResetClick() {
  if (!resetArmed.value) {
    resetArmed.value = true
    clearTimeout(disarmTimer)
    disarmTimer = setTimeout(() => (resetArmed.value = false), 4000)
    return
  }
  clearTimeout(disarmTimer)
  resetArmed.value = false
  isResetting.value = true
  try {
    await resetDatabase()
    // The session-side views of the wiped data should reset too, and the
    // session goes back to its fresh (idle) state.
    uploadHistory.clear()
    chatSession.reset()
    propertyData.value = null
    loadState.value = 'idle'
    sessionActive.value = false
    sessionDocTypes.value = new Set()
    sessionImageIds.value = new Set()
    explicitLookup.value = false
    toasts.success('Database reset — upload fresh documents to start over.')
  } catch (err) {
    toasts.error(`Reset failed: ${err.message}`)
  } finally {
    isResetting.value = false
  }
}
</script>

<template>
  <div class="dashboard-wrapper">
    <Sidebar :active-tab="activeTab" @select="activeTab = $event" />

    <div class="dashboard-main">
      <header class="dashboard-header">
        <BrandLogo :size="46" />

        <form class="search-bar" @submit.prevent="onSearchSubmit">
          <span class="search-icon"><AppIcon name="search" :size="14" /></span>
          <input
            v-model="searchInput"
            type="text"
            inputmode="numeric"
            placeholder="Jump to property ID…"
            aria-label="Jump to property ID"
          />
        </form>

        <div class="header-actions">
          <span class="property-pill">Property #{{ propertyId }}</span>
          <button
            class="icon-btn"
            :class="{ spinning: isRefreshing }"
            :disabled="isRefreshing"
            aria-label="Refresh property data"
            title="Refresh property data"
            @click="onManualRefresh"
          >
            <AppIcon name="refresh" :size="15" />
          </button>
          <button
            class="header-reset-btn"
            :class="{ armed: resetArmed }"
            :disabled="isResetting"
            :aria-label="resetArmed ? 'Click again to confirm database reset' : 'Reset database'"
            :title="resetArmed ? 'Click again to confirm' : 'Reset database for fresh uploads'"
            @click="onResetClick"
          >
            <AppIcon name="trash" :size="14" />
            <span v-if="resetArmed">Confirm reset</span>
            <span v-else-if="isResetting">Resetting…</span>
          </button>
          <ThemeToggle />
        </div>
      </header>

      <p class="caption error-banner" v-if="loadError">
        <AppIcon name="alert" :size="13" /> {{ loadError }}
      </p>

      <div v-show="activeTab === 'dashboard'" class="dashboard-columns">
        <section class="column" aria-label="Upload">
          <FileUpload :property-id="propertyId" @ingested="onIngested" />
        </section>

        <section class="column" aria-label="Property details">
          <PropertyCard
            :data="propertyData"
            :images="visibleImages"
            :valuation="showValuation ? propertyData?.valuation : {}"
            :loading="loadState === 'loading'"
            :not-found="loadState === 'notfound'"
            :show-specs="showSpecs"
            :show-valuation="showValuation"
            @refresh="refreshProperty"
          />
          <RenovationTable :renovations="visibleRenovations" />
        </section>

        <section class="column chat-column" aria-label="Chat">
          <ChatPanel :property-id="propertyId" />
        </section>
      </div>

      <div v-show="activeTab === 'upload'" class="focus-view">
        <FileUpload :property-id="propertyId" @ingested="onIngested" />
      </div>

      <div v-show="activeTab === 'chat'" class="focus-view chat-focus">
        <ChatPanel :property-id="propertyId" />
      </div>

      <div v-if="activeTab === 'settings'" class="focus-view">
        <div class="settings-panel">
          <h2>Settings</h2>
          <div class="settings-row">
            <div>
              <div class="settings-label">Appearance</div>
              <div class="caption">Switch between light and dark mode. Your choice is saved on this device.</div>
            </div>
            <ThemeToggle />
          </div>
          <div class="settings-row">
            <div>
              <div class="settings-label">Backend API</div>
              <div class="caption">http://127.0.0.1:8000 — FastAPI ingestion, valuation and warranty-RAG endpoints.</div>
            </div>
            <span class="status-chip" :class="loadState === 'error' ? 'offline' : 'online'">
              {{ loadState === 'error' ? 'Unreachable' : 'Connected' }}
            </span>
          </div>
          <div class="settings-row">
            <div>
              <div class="settings-label">Active property</div>
              <div class="caption">All uploads, valuations and warranty questions are scoped to this property.</div>
            </div>
            <span class="property-pill">#{{ propertyId }}</span>
          </div>
          <div class="settings-row">
            <div>
              <div class="settings-label">Reset data</div>
              <div class="caption">
                Deletes all ingested property data (photos, blueprint fields, inspection forms) for fresh uploads.
                The contractor directory and the warranty knowledge base are kept.
              </div>
            </div>
            <button
              class="danger-btn"
              :class="{ armed: resetArmed }"
              :disabled="isResetting"
              @click="onResetClick"
            >
              <AppIcon name="alert" :size="13" v-if="resetArmed" />
              {{ isResetting ? 'Resetting…' : resetArmed ? 'Click again to confirm' : 'Reset database' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <ToastHost />
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
  gap: 24px;
}

.search-bar {
  flex: 1;
  max-width: 420px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 999px;
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
}

.search-bar input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--color-text-main);
  font-size: var(--text-base);
  outline: none;
}

.search-icon {
  display: flex;
  color: var(--color-text-muted);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.property-pill {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 5px 12px;
  white-space: nowrap;
}

.icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--color-border);
  background-color: var(--color-bg-card);
  color: var(--color-text-main);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease;
}

.icon-btn:disabled {
  opacity: 0.6;
}

.icon-btn.spinning {
  animation: spin 0.8s linear infinite;
}

/* Header reset: icon-sized at rest, expands with a confirm label when
   armed. Same two-step handler as the Settings row's button. */
.header-reset-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  min-width: 32px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background-color: var(--color-bg-card);
  color: var(--color-danger);
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.header-reset-btn:hover:not(:disabled),
.header-reset-btn.armed {
  background-color: var(--color-danger);
  border-color: var(--color-danger);
  color: #fff;
}

.header-reset-btn:disabled {
  opacity: 0.6;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-banner {
  color: var(--color-danger);
  display: flex;
  align-items: center;
  gap: 6px;
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

.focus-view {
  flex: 1;
  min-height: 0;
  max-width: 720px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.chat-focus {
  overflow: hidden;
}

.settings-panel {
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 0;
  border-bottom: 1px solid var(--color-border);
}

.settings-row:last-child {
  border-bottom: none;
}

.settings-label {
  font-size: var(--text-base);
  font-weight: 600;
  margin-bottom: 2px;
}

.status-chip {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: var(--text-xs);
  font-weight: 500;
  white-space: nowrap;
}

.status-chip.online {
  color: var(--color-success);
  background-color: color-mix(in srgb, var(--color-success) 15%, transparent);
}

.status-chip.offline {
  color: var(--color-danger);
  background-color: color-mix(in srgb, var(--color-danger) 15%, transparent);
}

.danger-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-control);
  border: 1px solid color-mix(in srgb, var(--color-danger) 45%, var(--color-border));
  background-color: transparent;
  color: var(--color-danger);
  font-size: var(--text-sm);
  font-weight: 600;
  white-space: nowrap;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.danger-btn:hover:not(:disabled),
.danger-btn.armed {
  background-color: var(--color-danger);
  color: #fff;
}

.danger-btn:disabled {
  opacity: 0.6;
}

@media (max-width: 960px) {
  .dashboard-columns {
    grid-template-columns: 1fr;
  }
}
</style>
