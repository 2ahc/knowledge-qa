import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../views/Login.vue') },
    {
      path: '/',
      component: () => import('../views/Layout.vue'),
      children: [
        { path: '', redirect: '/chat' },
        { path: 'chat', component: () => import('../views/Chat.vue') },
        { path: 'knowledge', component: () => import('../views/Knowledge.vue') },
        { path: 'eval', component: () => import('../views/Eval.vue') },
        { path: 'admin', component: () => import('../views/Admin.vue'), meta: { admin: true } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/chat' },
  ],
})

router.beforeEach(async (to) => {
  const token = localStorage.getItem('access_token')
  if (!token && to.path !== '/login') return '/login'
  if (token && to.path === '/login') return '/chat'
  return true
})

export default router
