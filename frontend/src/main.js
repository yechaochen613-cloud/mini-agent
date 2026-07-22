import { createApp } from 'vue'
import naive from 'naive-ui'
import { MotionPlugin } from '@vueuse/motion'
import App from './App.vue'
import 'katex/dist/katex.min.css'
import './style.css'

const app = createApp(App)
app.use(naive)
app.use(MotionPlugin)
app.mount('#app')
