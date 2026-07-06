<script setup>
// Theme-aware brand lockup, drawn inline so it stays crisp at any size
// and recolors itself through the CSS theme variables — no light/dark
// asset swapping (the previous PNG pair needed a MutationObserver and
// two <img> tags to switch on theme change).
//
// The mark is a transom fanlight — the arched window above a door that
// the app is named for.
defineProps({
  size: { type: Number, default: 44 },
  showText: { type: Boolean, default: true },
})
</script>

<template>
  <div class="brand-lockup">
    <svg
      :width="size"
      :height="size"
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      class="brand-mark-svg"
    >
      <rect x="0" y="0" width="48" height="48" rx="12" class="mark-bg" />
      <!-- Fanlight: baseline, arch, and three radiating muntins -->
      <g class="mark-lines">
        <path d="M 10 33 H 38" />
        <path d="M 11 33 A 13 13 0 0 1 37 33" />
        <path d="M 24 33 L 24 20" />
        <path d="M 24 33 L 14.8 23.8" />
        <path d="M 24 33 L 33.2 23.8" />
      </g>
    </svg>

    <span class="brand-text" v-if="showText">
      <span class="brand-word">TRANSOM</span>
      <span class="brand-tagline">Property Intelligence</span>
    </span>
  </div>
</template>

<style scoped>
.brand-lockup {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.mark-bg {
  fill: var(--color-primary);
}

/* Stroke with the card background color: white lines on the blue mark in
   light mode, near-black lines on the cyan mark in dark mode — high
   contrast in both without any theme-conditional logic here. */
.mark-lines path {
  stroke: var(--color-bg-card);
  stroke-width: 2.6;
  stroke-linecap: round;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1;
}

.brand-word {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: var(--color-text-main);
}

.brand-tagline {
  font-size: 0.55rem;
  font-weight: 600;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}
</style>
