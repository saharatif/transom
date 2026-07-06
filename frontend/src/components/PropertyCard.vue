<script setup>
import { computed, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import { apiUrl } from '../api/client'
import { useToasts } from '../composables/useToasts'

const props = defineProps({
  data: { type: Object, default: null },
  // Session-scoped photo list, filtered by App.vue — NOT data.images
  // directly (that's every photo ever stored for the property).
  images: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  notFound: { type: Boolean, default: false },
  // Session gating (set by App.vue): specs (beds/baths/sqft) come from
  // blueprint uploads; valuation/builder/year/address come from
  // inspection uploads. Each stays hidden until its doc type has been
  // uploaded this session, so a photos-only session doesn't reveal data
  // stored by earlier sessions.
  showSpecs: { type: Boolean, default: true },
  showValuation: { type: Boolean, default: true },
})
defineEmits(['refresh'])

const toasts = useToasts()

const property = computed(() => props.data?.property)

// Only photos actually uploaded (served back by the API as their blurred
// _safe copies) — no static placeholder imagery. First photo is the
// hero; the rest become thumbnails.
const heroUrl = computed(() => (props.images.length ? apiUrl(props.images[0].url) : null))
const thumbnails = computed(() => props.images.slice(1))

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

const copied = ref(false)

async function copyPropertyId() {
  const p = property.value
  if (!p) return
  try {
    await navigator.clipboard.writeText(String(p.id))
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    toasts.error('Could not access the clipboard.')
  }
}

function openHeroPhoto() {
  if (heroUrl.value) window.open(heroUrl.value, '_blank', 'noopener')
}
</script>

<template>
  <div class="property-card">
    <div class="card-ribbon">
      <span class="column-title">{{ property ? `Property #${property.id}` : 'Property' }}</span>
      <span class="ribbon-location" v-if="property?.city_state_zip">
        <AppIcon name="pin" :size="11" /> {{ property.city_state_zip }}
      </span>
    </div>

    <div class="carousel" v-if="heroUrl">
      <img :src="heroUrl" alt="Primary uploaded photo of the property" class="hero-img" />
      <div class="thumb-strip" v-if="thumbnails.length">
        <img
          v-for="(thumb, i) in thumbnails"
          :key="thumb.id"
          :src="apiUrl(thumb.url)"
          class="thumb-img"
          :alt="`Uploaded property photo ${i + 2}`"
        />
      </div>
    </div>
    <div class="carousel-placeholder" v-else-if="property && !loading">
      <AppIcon name="camera" :size="20" />
      <span class="caption">No photos uploaded yet</span>
    </div>

    <!-- Skeleton while the first fetch is in flight, so the card doesn't
         flash the empty state before data lands. -->
    <div class="card-body" v-if="loading" aria-label="Loading property data">
      <div class="skeleton sk-title"></div>
      <div class="skeleton sk-line"></div>
      <div class="sk-badges">
        <div class="skeleton sk-badge"></div>
        <div class="skeleton sk-badge"></div>
        <div class="skeleton sk-badge"></div>
      </div>
    </div>

    <div class="card-body" v-else-if="property">
      <div class="title-row">
        <h2>{{ showValuation ? title : `Property #${property.id}` }}</h2>
        <span
          v-if="showValuation"
          class="price"
          :class="{ pending: priceLabel === 'Value pending' }"
        >{{ priceLabel }}</span>
      </div>

      <div class="address-row caption" v-if="showValuation">
        <AppIcon name="pin" :size="12" /> {{ addressLine }}
      </div>

      <div class="badges" v-if="showSpecs">
        <span class="badge">{{ property.bedrooms ?? '—' }} Bed</span>
        <span class="badge">{{ property.bathrooms ?? '—' }} Bath</span>
        <span class="badge">{{ property.sqft ? property.sqft.toLocaleString() : '—' }} sqft</span>
      </div>

      <div class="meta-row caption" v-if="showValuation && (property.builder || property.year_built)">
        <span v-if="property.builder">{{ property.builder }}</span>
        <span v-if="property.year_built">Built {{ property.year_built }}</span>
      </div>

      <span class="status-pin" v-if="showSpecs">Available</span>

      <p class="caption" v-if="!showSpecs">
        Upload a blueprint to see size and rooms; an inspection form adds valuation and renovation priorities.
      </p>
      <p class="caption" v-else-if="!showValuation">
        Upload a filled inspection form to see valuation, builder details and renovation priorities.
      </p>

      <div class="quick-actions">
        <span class="quick-actions-label caption">Quick Actions</span>
        <div class="quick-actions-row">
          <button class="quick-action-btn" title="Refresh property data" aria-label="Refresh property data" @click="$emit('refresh')">
            <AppIcon name="refresh" :size="14" />
          </button>
          <button
            v-if="heroUrl"
            class="quick-action-btn"
            title="Open primary photo"
            aria-label="Open primary photo"
            @click="openHeroPhoto"
          >
            <AppIcon name="camera" :size="14" />
          </button>
          <button class="quick-action-btn" title="Copy property ID" aria-label="Copy property ID" @click="copyPropertyId">
            <AppIcon :name="copied ? 'check' : 'copy'" :size="14" />
          </button>
          <span class="copy-status caption" v-if="copied">Copied!</span>
        </div>
      </div>
    </div>

    <div class="card-body empty-state" v-else>
      <p class="caption" v-if="notFound">
        No property with this ID yet — it's created automatically on the first upload.
      </p>
      <p class="caption" v-else>
        No property data yet — upload photos, a blueprint, or an inspection form to get started.
      </p>
    </div>
  </div>
</template>

<style scoped>
.property-card {
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  flex-shrink: 0;
}

.card-ribbon {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background-color: var(--color-bg-inset);
  border-bottom: 1px solid var(--color-border);
}

.ribbon-location {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

.carousel {
  display: flex;
  flex-direction: column;
}

.carousel-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 16px;
  color: var(--color-text-muted);
  background-color: var(--color-bg-inset);
  border-bottom: 1px solid var(--color-border);
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
  border-radius: var(--radius-control);
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
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--color-primary);
  white-space: nowrap;
}

.price.pending {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-muted);
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
  background-color: var(--color-bg-inset);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 3px 8px;
  font-size: var(--text-sm);
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
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--color-success);
  background-color: color-mix(in srgb, var(--color-success) 15%, transparent);
}

.quick-actions {
  margin-top: 6px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.quick-actions-label {
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.quick-actions-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.quick-action-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-control);
  border: 1px solid var(--color-border);
  background-color: var(--color-bg-inset);
  color: var(--color-text-main);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease;
}

.quick-action-btn:hover {
  background-color: color-mix(in srgb, var(--color-primary) 10%, var(--color-bg-inset));
}

.copy-status {
  color: var(--color-primary);
}

.empty-state {
  align-items: center;
  text-align: center;
  padding: 32px 16px;
}

/* Skeleton shapes */
.sk-title {
  height: 20px;
  width: 60%;
}

.sk-line {
  height: 12px;
  width: 40%;
}

.sk-badges {
  display: flex;
  gap: 8px;
}

.sk-badge {
  height: 24px;
  width: 64px;
}
</style>
