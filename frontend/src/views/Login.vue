<template>
  <div class="login-wrap">
    <!-- 右上：一笔极浅淡墨远山剪影（装饰，低透明度） -->
    <svg class="mountains" viewBox="0 0 600 260" preserveAspectRatio="xMidYMax meet" aria-hidden="true">
      <path
        d="M0 260 L120 118 Q160 74 200 118 L268 196 L330 128 Q368 88 406 128 L520 252 L600 260 Z"
        fill="#a6a199"
        opacity="0.16"
      />
      <path
        d="M140 260 L262 128 Q300 86 338 128 L470 268 L600 200 L600 260 Z"
        fill="#6e6a63"
        opacity="0.10"
      />
    </svg>

    <!-- 左下：登录内容，非对称偏置 -->
    <div class="login-content">
      <SealLogo :size="48" />
      <h1>企业知识问答</h1>
      <p class="sub">基于企业知识库的智能问答系统</p>

      <el-form @submit.prevent="onSubmit" label-position="top" class="login-form">
        <el-form-item label="用户名">
          <el-input
            v-model="username"
            size="large"
            class="ink-input"
            autocomplete="username"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            size="large"
            class="ink-input"
            show-password
            autocomplete="current-password"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="onSubmit">
          登 录
        </el-button>
        <p class="switch-line">
          还没有账号？<a class="switch-link" @click="router.push('/register')">注册一个</a>
        </p>
      </el-form>
    </div>

    <div class="copyright">企业知识问答 · 内部系统</div>
  </div>
</template>

<script setup lang="ts">
// 登录页：水墨非对称构图。内容偏置左下，右上淡墨远山，无卡片无投影。
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import SealLogo from '../components/SealLogo.vue'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)

async function onSubmit() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    ElMessage.success('登录成功')
    router.push('/chat')
  } catch {
    /* 登录失败的提示由 axios 拦截器统一弹出 */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  position: relative;
  min-height: 100dvh;
  background: var(--bg);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 远山装饰：右上偏置，不抢内容 */
.mountains {
  position: absolute;
  top: 6vh;
  right: 0;
  width: min(52vw, 640px);
  pointer-events: none;
}
/* 内容整体居中 */
.login-content {
  position: relative;
  width: 360px;
}
h1 {
  margin: 22px 0 6px;
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--ink);
}
.sub {
  color: var(--ink-3);
  font-size: 13px;
  letter-spacing: 0.06em;
  margin: 0 0 42px;
}
/* 标签在输入框上方；输入框无底色无边框，仅底部极细墨线 */
.login-form :deep(.el-form-item__label) {
  color: var(--ink-2);
  font-size: 13px;
  padding-bottom: 4px;
  line-height: 1.4;
}
.login-form :deep(.el-form-item) {
  margin-bottom: 26px;
}
.ink-input :deep(.el-input__wrapper) {
  background: transparent;
  box-shadow: none;
  border-radius: 0;
  border-bottom: 1px solid var(--ink-3);
  padding-left: 2px;
  transition: border-color 0.25s;
}
.ink-input :deep(.el-input__wrapper.is-focus) {
  border-bottom-color: var(--ink);
}
.ink-input :deep(.el-input__inner) {
  color: var(--ink);
}
/* 主按钮：墨底白字通栏 */
.login-btn {
  width: 100%;
  margin-top: 10px;
  height: 46px;
  font-size: 15px;
  letter-spacing: 0.5em;
  text-indent: 0.5em;
}
/* 登录/注册切换：一行淡墨小字 */
.switch-line {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
  color: var(--ink-3);
}
.switch-link {
  color: var(--ink);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 4px;
}
.copyright {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 4vh;
  text-align: center;
  font-size: 12px;
  color: var(--ink-3);
  letter-spacing: 0.08em;
}
</style>
