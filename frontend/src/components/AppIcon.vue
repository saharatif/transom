<script setup>
// Single source for all UI iconography — inline stroke SVGs (24x24
// viewBox, currentColor) instead of emoji, so icons render identically
// across platforms and inherit each context's text color.
const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 16 },
})

const PATHS = {
  home: 'M3 10.5 12 3l9 7.5M5 9.5V21h5v-6h4v6h5V9.5',
  upload: 'M12 16V4m0 0 -4.5 4.5M12 4l4.5 4.5M4 20h16',
  chat: 'M21 12a8 8 0 0 1-8 8H4l1.7-3A8 8 0 1 1 21 12Z',
  settings:
    'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm7.5-3.5.9-2.4-2-1.6.1-2.6-2.5-.6-1.2-2.3-2.8 1-2.8-1-1.2 2.3-2.5.6.1 2.6-2 1.6.9 2.4-.9 2.4 2 1.6-.1 2.6 2.5.6 1.2 2.3 2.8-1 2.8 1 1.2-2.3 2.5-.6-.1-2.6 2-1.6-.9-2.4Z',
  search: 'M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15Zm10.5 3-5.2-5.2',
  refresh: 'M20 12a8 8 0 1 1-2.34-5.66M20 4v4.5h-4.5',
  camera:
    'M4 8h3l2-2.5h6L17 8h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Zm8 9a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
  copy: 'M9 9h11v12H9V9Zm-2 8H4V3h11v3',
  pin: 'M12 21s-7-6.1-7-11a7 7 0 1 1 14 0c0 4.9-7 11-7 11Zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  sun: 'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-15v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11Z',
  check: 'M4.5 12.5 10 18 19.5 6.5',
  alert: 'M12 3 2.5 20h19L12 3Zm0 7v4.5m0 3v.5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13.5V12l3.5 2',
  cloud:
    'M7 19a5 5 0 0 1-.9-9.92A6 6 0 0 1 17.8 8.6 4.5 4.5 0 0 1 17.5 19H7Zm5-8v6m0-6-2.5 2.5M12 11l2.5 2.5',
  send: 'M4 12 20 4l-4 16-4.5-6.5L4 12Zm7.5 1.5L20 4',
  file: 'M6 3h8l4 4v14H6V3Zm8 0v4h4M9 12h6M9 16h6',
  image: 'M4 5h16v14H4V5Zm3 10 3.5-4 3 3.5 2-2.5L19 15M9 9.5h.01',
  bot: 'M12 5V2.5M8 9h8a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Zm1.5 4.5h.01m4.99 0h.01M3.5 13v3m17-3v3',
  user: 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7.5 10a7.5 7.5 0 0 1 15 0',
  'chevron-up': 'M6 15l6-6 6 6',
  'chevron-down': 'M6 9l6 6 6-6',
  external: 'M14 4h6v6m0-6L10 14M20 14v6H4V4h6',
  trash: 'M4 7h16M9 7V4h6v3M6.5 7l1 13.5h9l1-13.5M10 11v6m4-6v6',
}
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="PATHS[name] || ''" />
  </svg>
</template>
