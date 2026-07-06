<script setup>
import { ref, computed, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { getContractors } from '../api/client'

const props = defineProps({
  renovations: { type: Array, default: () => [] },
})

// The inspection form's renovation categories ("Roof replacement", "HVAC
// system", ...) don't share exact strings with renovation_companies'
// seeded categories (schema.sql) — this maps one to the other so each row
// can look up a recommended contractor. Renovation types with no
// reasonable category match intentionally have no contractor rather than
// a mislabeled guess.
const CATEGORY_MAP = {
  'roof replacement': 'Curb Appeal & Exterior Upgrades',
  'hvac system': 'Essential System & Energy Updates',
  'kitchen remodel': 'Kitchen & Bathroom Updates',
  'bathroom updates': 'Kitchen & Bathroom Updates',
  'flooring refinish': 'Flooring & Square Footage Upgrades',
  'exterior / curb appeal': 'Curb Appeal & Exterior Upgrades',
  'paint (interior)': 'Interior Painting',
}

const rowKey = (category) => (category || '').toLowerCase()

// Full contractor list per mapped category (not just the first match) so
// a row's dropdown can offer every recommended contractor for that
// category, not just whichever one happened to load first.
const contractorsByCategory = ref({})
// User's picked contractor per renovation row. Keyed by the row's own
// (lowercased) category — reads and writes MUST use the same key: an
// earlier version wrote under the mapped contractor-category but read
// under the row category, so every re-render/sort snapped the dropdown
// back to the first option (BUGS.md #31).
const selectedContractor = ref({})

async function loadContractors() {
  const categories = new Set()
  for (const r of props.renovations) {
    const mapped = CATEGORY_MAP[rowKey(r.category)]
    if (mapped) categories.add(mapped)
  }
  for (const category of categories) {
    if (contractorsByCategory.value[category]) continue
    try {
      const { contractors } = await getContractors(category)
      contractorsByCategory.value = { ...contractorsByCategory.value, [category]: contractors }
    } catch (err) {
      console.error(err)
    }
  }
}

function contractorsFor(category) {
  const mapped = CATEGORY_MAP[rowKey(category)]
  return mapped ? contractorsByCategory.value[mapped] || [] : []
}

function selectedContractorFor(category) {
  const options = contractorsFor(category)
  if (!options.length) return ''
  return selectedContractor.value[rowKey(category)] ?? options[0].company_name
}

watch(() => props.renovations, loadContractors, { immediate: true })

// --- Sort + filter ---
const sortKey = ref('priority')
const sortDir = ref('asc')
const filterText = ref('')

function parseLeadingCost(cost) {
  const match = /(\d[\d,]*)/.exec(cost || '')
  return match ? parseInt(match[1].replace(/,/g, ''), 10) : Number.POSITIVE_INFINITY
}

function parseLeadingRoi(roi) {
  const match = /(\d+(?:\.\d+)?)/.exec(roi || '')
  return match ? parseFloat(match[1]) : -Infinity
}

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const visibleRenovations = computed(() => {
  let rows = props.renovations
  if (filterText.value.trim()) {
    const needle = filterText.value.trim().toLowerCase()
    rows = rows.filter((r) => rowKey(r.category).includes(needle))
  }

  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    let av, bv
    if (sortKey.value === 'category') {
      av = rowKey(a.category)
      bv = rowKey(b.category)
    } else if (sortKey.value === 'priority') {
      av = a.priority ?? Number.POSITIVE_INFINITY
      bv = b.priority ?? Number.POSITIVE_INFINITY
    } else if (sortKey.value === 'cost') {
      av = parseLeadingCost(a.cost)
      bv = parseLeadingCost(b.cost)
    } else if (sortKey.value === 'roi') {
      av = parseLeadingRoi(a.roi)
      bv = parseLeadingRoi(b.roi)
    }
    if (av < bv) return -1 * dir
    if (av > bv) return 1 * dir
    return 0
  })
})

const COLUMNS = [
  { key: 'category', label: 'Category' },
  { key: 'priority', label: 'Priority' },
  { key: 'cost', label: 'Est. Cost' },
  { key: 'roi', label: 'ROI' },
]

const PRIORITY_LABELS = { 1: 'Urgent', 2: 'Moderate', 3: 'Low' }
</script>

<template>
  <div class="reno-table-panel">
    <div class="panel-header">
      <h2>Renovation Priorities</h2>
      <div class="filter-bar" v-if="renovations.length">
        <span class="filter-icon"><AppIcon name="search" :size="12" /></span>
        <input v-model="filterText" type="text" placeholder="Filter by category…" aria-label="Filter renovations" />
      </div>
    </div>

    <table class="reno-table" v-if="renovations.length">
      <thead>
        <tr>
          <th scope="col" v-for="col in COLUMNS" :key="col.key" :aria-sort="sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined">
            <button class="sort-btn" @click="toggleSort(col.key)">
              {{ col.label }}
              <AppIcon
                v-if="sortKey === col.key"
                :name="sortDir === 'asc' ? 'chevron-up' : 'chevron-down'"
                :size="11"
              />
            </button>
          </th>
          <th scope="col">Contractor</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in visibleRenovations" :key="rowKey(r.category)">
          <td>{{ r.category }}</td>
          <td>
            <span class="priority-chip" :class="`p${r.priority}`">
              {{ PRIORITY_LABELS[r.priority] || 'Low' }}
            </span>
          </td>
          <td>{{ r.cost || '—' }}</td>
          <td>{{ r.roi || '—' }}</td>
          <td>
            <select
              v-if="contractorsFor(r.category).length"
              class="contractor-select"
              :aria-label="`Contractor for ${r.category}`"
              :value="selectedContractorFor(r.category)"
              @change="selectedContractor[rowKey(r.category)] = $event.target.value"
            >
              <option v-for="c in contractorsFor(r.category)" :key="c.id" :value="c.company_name">
                {{ c.company_name }}
              </option>
            </select>
            <span v-else>—</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="caption empty-state">
      No renovation data yet — upload a filled inspection form to see priorities here.
    </p>
  </div>
</template>

<style scoped>
.reno-table-panel {
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 16px;
  box-shadow: var(--shadow-card);
  flex-shrink: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background-color: var(--color-bg-inset);
  border: 1px solid var(--color-border);
}

.filter-bar input {
  border: none;
  background: transparent;
  color: var(--color-text-main);
  font-size: var(--text-xs);
  outline: none;
  width: 140px;
}

.filter-icon {
  display: flex;
  color: var(--color-text-muted);
}

.reno-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}

.sort-btn {
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--text-xs);
  font-weight: 500;
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.reno-table th {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid var(--color-border);
}

.reno-table td {
  padding: 10px 8px;
  font-size: var(--text-sm);
  border-bottom: 1px solid var(--color-border);
}

.reno-table tr:last-child td {
  border-bottom: none;
}

.contractor-select {
  border: 1px solid var(--color-border);
  background-color: var(--color-bg-inset);
  color: var(--color-text-main);
  border-radius: 6px;
  padding: 4px 6px;
  font-size: var(--text-xs);
  max-width: 160px;
}

.priority-chip {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: var(--text-xs);
  background-color: var(--color-bg-inset);
}

.priority-chip.p1 {
  color: var(--color-danger);
  background-color: color-mix(in srgb, var(--color-danger) 15%, transparent);
}

.priority-chip.p2 {
  color: var(--color-warning);
  background-color: color-mix(in srgb, var(--color-warning) 15%, transparent);
}

.empty-state {
  padding: 8px 0 0;
}
</style>
