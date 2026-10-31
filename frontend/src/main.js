import { createApp } from 'vue'
import { ElIcon, ElTag } from 'element-plus'
import 'element-plus/es/components/icon/style/css'
import 'element-plus/es/components/tag/style/css'

import App from './App.vue'
import './styles/base.css'

const app = createApp(App)

app.component(ElTag.name, ElTag)
app.component(ElIcon.name, ElIcon)
app.mount('#app')
