<script setup>
import { ref, computed } from 'vue'
import AppIcon from './AppIcon.vue'
import { uploadFile } from '../api/client'
import { useToasts } from '../composables/useToasts'
import { useUploadHistory } from '../composables/useUploadHistory'

const props = defineProps({
  propertyId: { type: [String, Number], required: true },
})
const emit = defineEmits(['ingested'])

const toasts = useToasts()
const { history, activeItems, startItem } = useUploadHistory()

const docType = ref('photo')
const isDragOver = ref(false)
const isUploading = ref(false)
const activeQueueTab = ref('active')

const docTypeLabels = {
  photo: 'Property Photo',
  blueprint: 'Blueprint',
  inspection: 'Inspection Form',
}

// Photos and blueprints commonly come as several files per property
// (multiple room photos, a Ground Floor + Upper Floor sheet, etc.), so
// those two accept multi-select/multi-drop. The inspection form is one
// physical document per property, so it stays single-file.
const multiFileTypes = new Set(['photo', 'blueprint'])
const allowsMultiple = computed(() => multiFileTypes.has(docType.value))

async function uploadOne(file, type) {
  const entry = startItem(file.name, docTypeLabels[type])
  try {
    const result = await uploadFile(type, props.propertyId, file)
    entry.status = 'complete'
    toasts.success(`${file.name} processed — property data updated.`)
    emit('ingested', { docType: type, result })
  } catch (err) {
    entry.status = 'failed'
    entry.error = err.message
    toasts.error(`${file.name}: ${err.message}`)
  }
}

async function handleFiles(fileList) {
  const files = allowsMultiple.value ? Array.from(fileList) : Array.from(fileList).slice(0, 1)
  if (!files.length) return

  // Capture the selected doc type NOW — an upload takes many seconds,
  // and reading docType.value again after the await would mis-attribute
  // the completed upload if the user switches chips mid-flight (which
  // also mis-unlocked session-gated panels in App.vue).
  const type = docType.value
  isUploading.value = true
  try {
    // Sequential, not parallel — each ingest call already triggers a
    // full OCR/Vision + redaction pipeline; running several at once
    // would just contend for the same rate limits.
    for (const file of files) {
      await uploadOne(file, type)
    }
  } finally {
    isUploading.value = false
  }
}

function onDrop(e) {
  isDragOver.value = false
  handleFiles(e.dataTransfer.files)
}

function onFileInput(e) {
  handleFiles(e.target.files)
  e.target.value = '' // allow re-selecting the same file(s) later
}

const STATUS_LABELS = { processing: 'Processing…', complete: 'Complete', failed: 'Failed' }
</script>

<template>
  <div class="upload-panel">
    <div class="panel-heading">
      <h2 class="column-title">Asset Ingestion Queue</h2>
    </div>

    <div class="doc-type-select" role="radiogroup" aria-label="Document type">
      <button
        v-for="(label, key) in docTypeLabels"
        :key="key"
        class="doc-type-btn"
        :class="{ active: docType === key }"
        role="radio"
        :aria-checked="docType === key"
        @click="docType = key"
      >
        {{ label }}
      </button>
    </div>

    <label
      class="drop-zone"
      :class="{ 'drag-over': isDragOver, uploading: isUploading }"
      @dragover.prevent="isDragOver = true"
      @dragleave.prevent="isDragOver = false"
      @drop.prevent="onDrop"
    >
      <input
        type="file"
        class="sr-only"
        accept="image/*,.pdf"
        :multiple="allowsMultiple"
        :disabled="isUploading"
        @change="onFileInput"
      />
      <span class="upload-icon"><AppIcon name="cloud" :size="30" /></span>
      <span class="drop-label">
        {{ isUploading ? 'Uploading…' : 'Drag files or click to upload' }}
      </span>
      <span class="caption">
        {{ docTypeLabels[docType] }}{{ allowsMultiple ? ' — multiple files allowed' : '' }}
      </span>
    </label>

    <div class="queue-section">
      <div class="queue-tabs" role="tablist">
        <button
          role="tab"
          :aria-selected="activeQueueTab === 'active'"
          class="queue-tab"
          :class="{ active: activeQueueTab === 'active' }"
          @click="activeQueueTab = 'active'"
        >
          Active Queue
          <span class="tab-count" v-if="activeItems.length">{{ activeItems.length }}</span>
        </button>
        <button
          role="tab"
          :aria-selected="activeQueueTab === 'history'"
          class="queue-tab"
          :class="{ active: activeQueueTab === 'history' }"
          @click="activeQueueTab = 'history'"
        >
          Upload History
        </button>
      </div>

      <div v-if="activeQueueTab === 'active'" class="queue-list">
        <div v-if="!activeItems.length" class="caption empty-state">
          Nothing in progress — completed uploads move to Upload History.
        </div>
        <div v-for="(row, i) in activeItems" :key="i" class="queue-row">
          <div class="queue-row-top">
            <span class="queue-icon"><AppIcon name="file" :size="13" /></span>
            <span class="queue-file truncate" :title="row.fileName">{{ row.fileName }}</span>
            <span class="caption">{{ row.docTypeLabel }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill indeterminate"></div>
          </div>
        </div>
      </div>

      <table class="history-table" v-else-if="history.length">
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">File</th>
            <th scope="col">Type</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in history" :key="i">
            <td>{{ row.time }}</td>
            <td class="truncate" :title="row.error ? `${row.fileName} — ${row.error}` : row.fileName">
              {{ row.fileName }}
            </td>
            <td class="caption">{{ row.docTypeLabel }}</td>
            <td>
              <span class="status-chip" :class="row.status">
                {{ STATUS_LABELS[row.status] }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="caption empty-state">No uploads yet this session.</p>
    </div>
  </div>
</template>

<style scoped>
.upload-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Matches the vertical text offset inside the other columns' header
   bars (1px card border + 10px padding), so all three column titles sit
   on one line. */
.panel-heading {
  padding-top: 11px;
}

.doc-type-select {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.doc-type-btn {
  border: 1px solid var(--color-border);
  background-color: var(--color-bg-card);
  color: var(--color-text-muted);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: var(--text-xs);
}

.doc-type-btn.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background-color: color-mix(in srgb, var(--color-primary) 10%, var(--color-bg-card));
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 32px 16px;
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-card);
  background-color: var(--color-bg-card);
  cursor: pointer;
  text-align: center;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.drop-zone.drag-over {
  border: 2px solid var(--color-primary);
  background-color: color-mix(in srgb, var(--color-primary) 8%, var(--color-bg-card));
}

.drop-zone.uploading {
  opacity: 0.7;
  cursor: progress;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}

.upload-icon {
  display: flex;
  color: var(--color-primary);
}

.drop-label {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--color-text-main);
}

.queue-section {
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 4px 4px 12px;
  box-shadow: var(--shadow-card);
}

.queue-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 8px 4px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 8px;
}

.queue-tab {
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 6px 4px 10px;
  border-bottom: 2px solid transparent;
  display: flex;
  align-items: center;
  gap: 6px;
}

.queue-tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-count {
  background-color: var(--color-primary);
  color: #fff;
  border-radius: 999px;
  padding: 0 6px;
  font-size: var(--text-xs);
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 12px;
}

.queue-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.queue-row-top {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
}

.queue-icon {
  display: flex;
  color: var(--color-text-muted);
}

.queue-file {
  max-width: 100%;
}

.progress-track {
  height: 4px;
  border-radius: 999px;
  background-color: var(--color-border);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: var(--color-primary);
  border-radius: 999px;
}

.progress-fill.indeterminate {
  width: 40%;
  animation: indeterminate 1.1s ease-in-out infinite;
}

@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(250%); }
}

.history-table {
  width: 100%;
  border-collapse: collapse;
}

.history-table th {
  text-align: left;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  font-weight: 500;
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border);
}

.history-table td {
  padding: 10px;
  font-size: var(--text-sm);
  border-bottom: 1px solid var(--color-border);
}

.history-table tr:last-child td {
  border-bottom: none;
}

.truncate {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: var(--text-xs);
  background-color: var(--color-bg-inset);
  color: var(--color-text-muted);
}

.status-chip.complete {
  color: var(--color-success);
  background-color: color-mix(in srgb, var(--color-success) 15%, transparent);
}

.status-chip.failed {
  color: var(--color-danger);
  background-color: color-mix(in srgb, var(--color-danger) 15%, transparent);
}

.status-chip.processing {
  color: var(--color-primary);
  background-color: color-mix(in srgb, var(--color-primary) 15%, transparent);
}

.empty-state {
  padding: 12px;
}
</style>
