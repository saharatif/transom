# Design Specification: Modern Property Dashboard (`DESIGN.MD`)

This document establishes the architecture, layout system, component behaviors, and design token configurations for the Modern Property Dashboard, providing seamless support for **Light Mode** and **Dark Mode** toggling.

---

## 1. Core Architecture & Theme Engine

The frontend is built with **Vue 3 (Composition API)** using localized, reactive state management or Pinia for theme-state synchronization. Theme switches inject class tokens onto the `<html>` or `<body>` element (`data-theme="light"` or `data-theme="dark"`), which rebind native CSS Custom Variables globally.

### Design Tokens (CSS Variables)

| Token Name | Light Mode Value | Dark Mode Value | Semantic Usage |
| :--- | :--- | :--- | :--- |
| `--color-bg-main` | `#FFFFFF` | `#1A1A1A` | Core canvas background |
| `--color-bg-sidebar`| `#F4F5F7` | `#121212` | Navigation rail container |
| `--color-bg-card` | `#F8F9FA` | `#242424` | Component containers |
| `--color-primary` | `#007BFF` | `#00CFFF` | Active states, major buttons |
| `--color-text-main`| `#212529` | `#E0E0E0` | Standard readable headers & body |
| `--color-text-muted`| `#6C757D` | `#A0A0A0` | Captions, metadata labels |
| `--color-border` | `#E2E8F0` | `#333333` | Layout dividers, component strokes |
| `--shadow-card` | `0 4px 12px rgba(0,0,0,0.05)`| `0 4px 16px rgba(0,0,0,0.4)`| Z-index structural elevation |

### Typography Blueprint
*   **Primary Font Family:** `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Sans-Serif;`
*   **Font Weights:** Regular (`400`), Medium (`500`), SemiBold (`600`), Bold (`700`).
*   **Scale:**
    *   `h1` (Dashboard Header): `24pt` / Line-height: `1.2`
    *   `h2` (Card Headers): `14pt` / Line-height: `1.3`
    *   `body` (Content text): `10pt` / Line-height: `1.5`
    *   `caption` (Metadata, timestamps): `8.5pt` / Line-height: `1.4`

---

## 2. Component Design & Functional Layouts

### A. Navigation Rail (Sidebar)
*   **Layout:** Slim, vertical icon-only left navigation bar utilizing flexible positioning to align primary navigation buttons at the top and system settings at the baseline.
*   **Interaction State:** Active tab transitions `--color-primary` to background or accent strip. Non-active items dynamically scale down contrast via opacity rules.

### B. Vue Upload UI Component
The interface implements an elegant file-ingestion container designed specifically for processing real-estate photographic assets.
*   **Drop Zone Architecture:**
    *   A dotted boundary border (`2px dashed var(--color-border)`) bounding an input surface area containing a stylized upload icon.
    *   **Dragover Hook:** Active canvas state overrides layout variables to display a solid `--color-primary` frame with low-opacity backdrop tinting.
*   **Upload History Data Grid:**
    *   Tabular log tracking current asset staging statuses (`Date`, `Location`, `Status`).
    *   Maintains consistent row padding (`12px`) with fine dividers to separate rows easily.

### C. Property Detail Card
Renders critical context regarding specialized property portfolios. Designed around the real-world property **5512 Maple St, McKinney, TX**.
*   **Asset Carousel Container:**
    *   Top section hosts an primary layout image highlighting external structures or entryways (e.g., *b4a24c6bba5ce5e09dea9d4c72d7c2bd-uncropped_scaled_within_1536_1152_2.jpg*).
    *   Sub-level strip renders three micro-thumbnails (`48px x 48px`, rounded aspect-ratio squares) depicting granular rooms like kitchens and living spaces (e.g., *4390af3f3447732e89b2906be3840777-uncropped_scaled_within_1536_1152_2.jpg*).
*   **Content Blueprint:**
    *   **Title/Price Segment:** Large bold text showcasing property value configurations adjacent to contextual naming headers.
    *   **Geographic Metadata:** Custom-spaced icon alignments linking address strings.
    *   **Attribute Badges:** Standard matrix blocks grouping parameters such as bedroom metrics (`3 Bed`), plumbing units (`2.5 Bath`), and floor dimensions (`2,100 sqft`).
    *   **Workflow State Pin:** Muted text chips with high-visibility backdrops denoting tracking status (e.g., `Available`, `Under Review`).

### D. Agent-Client Chat Stream View
*   **Header Section:** Explicit display parameters calling out client specific profiles (`Client: Sarah Jones`).
*   **Message Stream Layout:**
    *   **Inbound Layout (Agent):** Left-aligned blocks anchored by avatar components. Content boxes tinted via accent profiles (`--color-primary`) with inverse crisp contrast typography.
    *   **Outbound Layout (Client):** Right-aligned configurations utilizing high-contrast background tags suited for the active theme profile.
*   **Input Staging Area:** Bottom border-locked input bar incorporating dedicated actions alongside plain text fields.

### E. Global Theme Switcher (Toggle Switch)
*   **Visual Representation:** Floating pill-shaped switch component centered along horizontal top-axis boundaries.
*   **Animation Engine:** Smooth transform transitions (`cubic-bezier(0.4, 0, 0.2, 1)`) shifting decorative vector indicators between day/night variables instantly.

---

## 3. Vue 3 Implementation Blueprint

```vue
<script setup>
import { ref, onMounted } from 'vue'

const isDarkMode = ref(false)

const toggleTheme = () => {
  isDarkMode.value = !isDarkMode.value
  document.documentElement.setAttribute('data-theme', isDarkMode.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light')
}

onMounted(() => {
  const savedTheme = localStorage.getItem('theme') || 'light'
  isDarkMode.value = savedTheme === 'dark'
  document.documentElement.setAttribute('data-theme', savedTheme)
})
</script>

<template>
  <div class="dashboard-wrapper">
    <!-- Theme Toggle Control -->
    <button @click="toggleTheme" class="theme-toggle-btn">
      <span v-if="isDarkMode" class="icon-sun">☀️ Light Mode</span>
      <span v-else class="icon-moon">🌙 Dark Mode</span>
    </button>
    
    <!-- Dashboard Contents Go Here -->
  </div>
</template>

<style scoped>
/* Scoped layout handles fallback parameters mapped to custom structural classes */
.dashboard-wrapper {
  background-color: var(--color-bg-main);
  color: var(--color-text-main);
  transition: background-color 0.3s ease, color 0.3s ease;
}
</style>
```

---

## 4. Production Accessibility Standards
1.  **Contrast Compliance:** Ensure all interactive elements achieve a minimum AAA text-contrast score against standard background variables.
2.  **Focus States:** Use a distinct outer outline (`2px solid var(--color-primary)`) when navigating with a keyboard to keep track of the active element.
3.  **Screen Readers:** Maintain descriptive alternative markup attributes for real-estate carousel previews to ensure accurate context tracking.
