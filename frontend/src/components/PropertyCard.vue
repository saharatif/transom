<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, default: null },
})

// Reference photography per design/DESIGN.md's Property Detail Card spec
// (hero + 3 room thumbnails), copied into public/images/.
const heroImage = '/images/b4a24c6bba5ce5e09dea9d4c72d7c2bd-uncropped_scaled_within_1536_1152.webp'
const thumbnails = [
  '/images/4390af3f3447732e89b2906be3840777-uncropped_scaled_within_1536_1152.webp',
  '/images/708cdc9e152a595316da42728bda6bcf-uncropped_scaled_within_1536_1152.webp',
  '/images/880c2a3c89a11a8ed4090b8b88bc1ecc-uncropped_scaled_within_1536_1152.webp',
]

const property = computed(() => props.data?.property)

const title = computed(() => {
  const p = property.value
  if (!p) return 'Property'
  return p.address ? `Property, ${p.address}` : `Property #${p.id}`
})

const priceLabel = computed(() => {
  const v = property.value?.estimated_value ?? property.value?.listed_price
  if (!v) return 'Value pending'
  return `$${Number(v).toLocaleString()}`
})

const addressLine = computed(() => {
  const p = property.value
  if (!p) return ''
  return [p.address, p.city_state_zip].filter(Boolean).join(', ') || 'Address not yet captured'
})
</script>

<template>
  <div class="property-card">
    <div class="carousel">
      <img :src="heroImage" alt="Primary exterior photo of the property" class="hero-img" />
      <div class="thumb-strip">
        <img
          v-for="(thumb, i) in thumbnails"
          :key="i"
          :src="thumb"
          class="thumb-img"
          :alt="`Interior room photo ${i + 1}`"
        />
      </div>
    </div>

    <div class="card-body" v-if="property">
      <div class="title-row">
        <h2>{{ title }}</h2>
        <span class="price">{{ priceLabel }}</span>
      </div>

      <div class="address-row caption">
        <span aria-hidden="true">&#128205;</span> {{ addressLine }}
      </div>

      <div class="badges">
        <span class="badge">{{ property.bedrooms ?? '—' }} Bed</span>
        <span class="badge">{{ property.bathrooms ?? '—' }} Bath</span>
        <span class="badge">{{ property.sqft ? property.sqft.toLocaleString() : '—' }} sqft</span>
      </div>

      <div class="meta-row caption" v-if="property.builder || property.year_built">
        <span v-if="property.builder">{{ property.builder }}</span>
        <span v-if="property.year_built">Built {{ property.year_built }}</span>
      </div>

      <span class="status-pin">Available</span>
    </div>

    <div class="card-body empty-state" v-else>
      <p class="caption">No property data yet — upload photos, a blueprint, or an inspection form to get started.</p>
    </div>
  </div>
</template>

<style scoped>
.property-card {
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  box-shadow: var(--shadow-card);
  overflow: hidden;
  flex-shrink: 0;
}

.carousel {
  display: flex;
  flex-direction: column;
}

.hero-img {
  width: 100%;
  height: 160px;
  object-fit: cover;
  display: block;
}

.thumb-strip {
  display: flex;
  gap: 6px;
  padding: 8px;
}

.thumb-img {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--color-border);
}

.card-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.price {
  font-size: 13pt;
  font-weight: 700;
  color: var(--color-primary);
  white-space: nowrap;
}

.address-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.badge {
  background-color: var(--color-bg-main);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 9pt;
}

.meta-row {
  display: flex;
  gap: 12px;
}

.status-pin {
  align-self: flex-start;
  margin-top: 4px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 8.5pt;
  font-weight: 500;
  color: #1a7f37;
  background-color: color-mix(in srgb, #1a7f37 15%, transparent);
}

.empty-state {
  align-items: center;
  text-align: center;
  padding: 32px 16px;
}
</style>
