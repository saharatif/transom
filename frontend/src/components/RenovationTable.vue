<script setup>
import { ref, watch } from 'vue'
import { getContractors } from '../api/client'

const props = defineProps({
  renovations: { type: Array, default: () => [] },
})

// The inspection form's renovation categories ("Roof replacement", "HVAC
// system", ...) don't share exact strings with renovation_companies'
// seeded categories (schema.sql) — this maps one to the other so each row
// can look up a recommended contractor. Renovation types with no
// reasonable category match (e.g. "Paint (interior)") intentionally have
// no contractor rather than a mislabeled guess.
const CATEGORY_MAP = {
  'roof replacement': 'Curb Appeal & Exterior Upgrades',
  'hvac system': 'Essential System & Energy Updates',
  'kitchen remodel': 'Kitchen & Bathroom Updates',
  'bathroom updates': 'Kitchen & Bathroom Updates',
  'flooring refinish': 'Flooring & Square Footage Upgrades',
  'exterior / curb appeal': 'Curb Appeal & Exterior Upgrades',
}

const contractorByCategory = ref({})

async function loadContractors() {
  const categories = new Set()
  for (const r of props.renovations) {
    const mapped = CATEGORY_MAP[(r.category || '').toLowerCase()]
    if (mapped) categories.add(mapped)
  }
  for (const category of categories) {
    if (contractorByCategory.value[category]) continue
    try {
      const { contractors } = await getContractors(category)
      contractorByCategory.value = {
        ...contractorByCategory.value,
        [category]: contractors[0]?.company_name ?? null,
      }
    } catch (err) {
      console.error(err)
    }
  }
}

function contractorFor(category) {
  const mapped = CATEGORY_MAP[(category || '').toLowerCase()]
  return mapped ? contractorByCategory.value[mapped] : null
}

watch(() => props.renovations, loadContractors, { immediate: true })
</script>

<template>
  <div class="reno-table-panel">
    <h2>Renovation Priorities</h2>
    <table class="reno-table" v-if="renovations.length">
      <thead>
        <tr>
          <th scope="col">Category</th>
          <th scope="col">Priority</th>
          <th scope="col">Est. Cost</th>
          <th scope="col">ROI</th>
          <th scope="col">Contractor</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(r, i) in renovations" :key="i">
          <td>{{ r.category }}</td>
          <td>
            <span class="priority-chip" :class="`p${r.priority}`">
              {{ r.priority === 1 ? 'Urgent' : r.priority === 2 ? 'Moderate' : 'Low' }}
            </span>
          </td>
          <td>{{ r.cost || '—' }}</td>
          <td>{{ r.roi || '—' }}</td>
          <td>{{ contractorFor(r.category) || '—' }}</td>
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
  border-radius: 12px;
  padding: 16px;
  box-shadow: var(--shadow-card);
  flex-shrink: 0;
}

.reno-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}

.reno-table th {
  text-align: left;
  font-size: 8.5pt;
  color: var(--color-text-muted);
  font-weight: 500;
  padding: 8px;
  border-bottom: 1px solid var(--color-border);
}

.reno-table td {
  padding: 10px 8px;
  font-size: 9pt;
  border-bottom: 1px solid var(--color-border);
}

.priority-chip {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 8pt;
  background-color: var(--color-bg-main);
}

.priority-chip.p1 {
  color: #d1242f;
  background-color: color-mix(in srgb, #d1242f 15%, transparent);
}

.priority-chip.p2 {
  color: #9a6700;
  background-color: color-mix(in srgb, #9a6700 15%, transparent);
}

.empty-state {
  padding: 8px 0 0;
}
</style>
