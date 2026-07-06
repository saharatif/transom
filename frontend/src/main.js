import { createApp } from 'vue'
import App from './App.vue'
// Inter (variable weight, self-hosted via @fontsource so it loads with
// no external requests) — the same typeface the brand lockup is set in.
// theme.css only *declared* Inter before; nothing ever loaded it, so
// the UI silently fell back to the system font.
import '@fontsource-variable/inter'
import './styles/theme.css'

createApp(App).mount('#app')
