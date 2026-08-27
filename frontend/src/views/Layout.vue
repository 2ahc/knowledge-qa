<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand" @click="$router.push('/chat')">
        <SealLogo :size="28" />
        <span class="brand-name">企业知识问答</span>
      </div>
      <el-menu
        mode="horizontal"
        :default-active="activeMenu"
        :ellipsis="false"
        class="nav"
        router
      >
        <el-menu-item index="/chat">智能问答</el-menu-item>
        <el-menu-item index="/knowledge">知识库管理</el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/eval">问答评测</el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/admin">管理后台</el-menu-item>
      </el-menu>
      <el-dropdown @command="onCommand">
        <span class="user">
          <el-avatar :size="28" class="avatar">{{ avatarText }}</el-avatar>
          {{ auth.user?.display_name || auth.user?.username || '...' }}
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>
              角色：{{ auth.isAdmin ? '管理员' : '普通用户' }}
            </el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </el-header>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
// 整体布局：顶部极简导航栏（印章 + 品牌名 + 菜单 + 头像）+ 主内容区。
// 导航当前项用墨黑下划线标识，不用高亮块；菜单项按角色过滤。
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import SealLogo from '../components/SealLogo.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => route.path)
const avatarText = computed(() => (auth.user?.display_name || auth.user?.username || 'U').slice(0, 1))

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}

onMounted(async () => {
  // 页面刷新后 user 丢失：用本地令牌拉取当前用户；失败（令牌无效）则回登录页
  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      router.push('/login')
    }
  }
})
</script>

<style scoped>
.layout {
  height: 100%;
}
/* 极简导航：纸底同色，仅一条极细底线分隔 */
.header {
  display: flex;
  align-items: center;
  background: var(--bg);
  border-bottom: 1px solid var(--line);
  padding: 0 28px;
  height: 56px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  white-space: nowrap;
}
.brand-name {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 17px;
  color: var(--ink);
  letter-spacing: 0.04em;
}
/* 导航：当前项墨黑加粗 + 极细墨黑下划线，不用高亮块 */
.nav {
  flex: 1;
  border-bottom: none;
  margin-left: 40px;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: var(--ink-2);
  --el-menu-active-color: var(--ink);
  --el-menu-hover-text-color: var(--ink);
  --el-menu-hover-bg-color: transparent;
}
.nav :deep(.el-menu-item) {
  font-size: 14px;
  letter-spacing: 0.02em;
  border-bottom-width: 1px;
  transition: color 0.2s;
}
.nav :deep(.el-menu-item.is-active) {
  font-weight: 600;
  border-bottom-color: var(--ink);
}
.user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--ink-2);
  white-space: nowrap;
  font-size: 13px;
}
/* 头像：墨黑圆 */
.avatar {
  background: var(--ink);
  color: #fdfcfa;
  font-size: 13px;
}
.main {
  padding: 0;
  overflow: hidden;
}
</style>
