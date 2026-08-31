// 路由配置：登录页独立，其余页面嵌在 Layout（左侧导航 + 右侧内容）内。
// 全部采用懒加载（动态 import），按需加载页面代码。
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../views/Login.vue') },
    { path: '/register', component: () => import('../views/Register.vue') },
    {
      path: '/',
      component: () => import('../views/Layout.vue'),
      children: [
        { path: '', redirect: '/chat' },
        { path: 'chat', component: () => import('../views/Chat.vue') },
        { path: 'knowledge', component: () => import('../views/Knowledge.vue') },
        { path: 'eval', component: () => import('../views/Eval.vue') },
        { path: 'admin', component: () => import('../views/Admin.vue'), meta: { admin: true } }, // 仅管理员可见（Layout 中按角色过滤菜单）
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/chat' },
  ],
})

// 登录页与注册页都无需令牌（注册接口本身不鉴权）
const PUBLIC_PATHS = ['/login', '/register']

// 全局路由守卫：未登录只能访问登录/注册页；已登录访问这两个页面则跳回聊天页
router.beforeEach(async (to) => {
  const token = localStorage.getItem('access_token')
  if (!token && !PUBLIC_PATHS.includes(to.path)) return '/login'
  if (token && PUBLIC_PATHS.includes(to.path)) return '/chat'
  return true
})

export default router
