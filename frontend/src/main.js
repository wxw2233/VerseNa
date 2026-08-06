import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import ChatView from './views/ChatView.vue'
import SettingsView from './views/SettingsView.vue'
import PetView from './views/PetView.vue'
import './styles/default.css'
import './assets/theme-base.css'
import './styles/design-system.css'
import './styles/accessibility.css'
import { installAuthFetchInterceptor } from './utils/auth'

installAuthFetchInterceptor()

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: ChatView },
    { path: '/settings', component: SettingsView },
    { path: '/pet', component: PetView },
  ]
})

createApp(App).use(createPinia()).use(router).mount('#app')
