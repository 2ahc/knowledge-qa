<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand" @click="$router.push('/chat')">
        <span class="logo">📚</span>
        <span>企业知识问答</span>
      </div>
      <el-menu
        mode="horizontal"
        :default-active="activeMenu"
        :ellipsis="false"
        class="nav"
        router
      >
        <el-menu-item index="/chat">💬 智能问答</el-menu-item>
        <el-menu-item index="/knowledge">📁 知识库管理</el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/eval">📊 问答评测</el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/admin">⚙️ 管理后台</el-menu-item>
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
// 整体布局：顶部导航栏（品牌 + 菜单 + 用户信息）+ 主内容区。
// 菜单项按角色过滤：评测与管理后台仅管理员可见。
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

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
.header {
  display: flex;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid var(--line);
  padding: 0 20px;
  height: 56px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 16px;
  cursor: pointer;
  white-space: nowrap;
}
.logo {
  font-size: 22px;
}
.nav {
  flex: 1;
  border-bottom: none;
  margin-left: 24px;
}
.user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--ink);
  white-space: nowrap;
}
.avatar {
  background: var(--brand);
  color: #fff;
  font-size: 13px;
}
.main {
  padding: 0;
  overflow: hidden;
}
</style>
