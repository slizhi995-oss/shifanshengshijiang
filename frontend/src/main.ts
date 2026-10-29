import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import 'virtual:uno.css'

import App from './App.vue'
import router from './router'
import './styles/main.css'

console.log('🚀 Starting app...')

const pinia = createPinia()
const app = createApp(App)

console.log('✅ Vue app created')

app.use(pinia)
console.log('✅ Pinia installed')

app.use(router)
console.log('✅ Router installed')

app.use(ElementPlus, {
  locale: zhCn,
})
console.log('✅ ElementPlus installed')

app.mount('#app')
console.log('✅ App mounted')
