<script setup>
import { ref } from 'vue'
import { uploadFile } from '../api/client'

const props = defineProps({
  propertyId: { type: [String, Number], required: true },
})
const emit = defineEmits(['ingested'])

const docType = ref('photo')
const isDragOver = ref(false)
const isUploading = ref(false)
// Upload history is tracked client-side for this session — the backend
// doesn't currently store an ingestion-event timestamp/log table, only
// the extracted results themselves (see backend/db/schema.sql).
const history = ref([])

const docTypeLabels = {
  photo: 'Property Photo',
  blueprint: 'Blueprint',
  inspection: 'Inspection Form',
}

async function handleFiles(fileList) {
  const file = fileList[0]
  if (!file) return

  const historyEntry = {
    date: new Date().toLocaleDateString(),
    location: file.name,
    status: 'Processing...',
  }
  history.value.unshift(historyEntry)
  isUploading.value = true

  try {
    const result = await uploadFile(docType.value, props.propertyId, file)
    historyEntry.status = 'Complete'
    emit('ingested', { docType: docType.value, result })
  } catch (err) {
    historyEntry.status = 'Failed'
    console.error(err)
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
}
</script>

<template>
  <div class="upload-panel">
    <h2>Upload a New Property</h2>

    <div class="doc-type-select">
      <button
        v-for="(label, key) in docTypeLabels"
        :key="key"
        class="doc-type-btn"
        :class="{ active: docType === key }"
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
        :disabled="isUploading"
        @change="onFileInput"
      />
      <span class="upload-icon" aria-hidden="true">&#9729;</span>
      <span class="drop-label">
        {{ isUploading ? 'Uploading…' : 'Drag files or click to upload' }}
      </span>
      <span class="caption">{{ docTypeLabels[docType] }}</span>
    </label>

    <div class="history-section">
      <h2>Upload History</h2>
      <table class="history-table" v-if="history.length">
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Location</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in history" :key="i">
            <td>{{ row.date }}</td>
            <td class="truncate" :title="row.location">{{ row.location }}</td>
            <td>
              <span class="status-chip" :class="row.status.toLowerCase().replace('...', '')">
                {{ row.status }}
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
  font-size: 8.5pt;
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
  border-radius: 12px;
  cursor: pointer;
  text-align: center;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.drop-zone.drag-over {
  border: 2px solid var(--color-primary);
  border-style: solid;
  background-color: color-mix(in srgb, var(--color-primary) 8%, transparent);
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
  font-size: 28px;
  color: var(--color-primary);
}

.drop-label {
  font-size: 10pt;
  color: var(--color-text-main);
}

.history-table {
  width: 100%;
  border-collapse: collapse;
}

.history-table th {
  text-align: left;
  font-size: 8.5pt;
  color: var(--color-text-muted);
  font-weight: 500;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
}

.history-table td {
  padding: 12px;
  font-size: 9pt;
  border-bottom: 1px solid var(--color-border);
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
  font-size: 8pt;
  background-color: var(--color-bg-card);
  color: var(--color-text-muted);
}

.status-chip.complete {
  color: #1a7f37;
  background-color: color-mix(in srgb, #1a7f37 15%, transparent);
}

.status-chip.failed {
  color: #d1242f;
  background-color: color-mix(in srgb, #d1242f 15%, transparent);
}

.status-chip.processing {
  color: var(--color-primary);
  background-color: color-mix(in srgb, var(--color-primary) 15%, transparent);
}

.empty-state {
  padding: 8px 0;
}
</style>
