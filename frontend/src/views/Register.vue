<template>
  <div class="login-wrap">
    <!-- 右上：一笔极浅淡墨远山剪影（与登录页同构图，保持系列感） -->
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

    <!-- 左下：注册内容，非对称偏置 -->
    <div class="login-content">
      <SealLogo :size="48" />
      <h1>创建账号</h1>
      <p class="sub">注册后即可使用知识库问答（普通用户）</p>

      <el-form @submit.prevent="onSubmit" label-position="top" class="login-form">
        <el-form-item label="用户名">
          <el-input
            v-model="username"
            size="large"
            class="ink-input"
            autocomplete="username"
            placeholder="2-20 位，字母 / 数字 / 下划线 / 中文"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-form-item label="显示名（选填）">
          <el-input
            v-model="displayName"
            size="large"
            class="ink-input"
            autocomplete="nickname"
            placeholder="留空则使用用户名"
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
            autocomplete="new-password"
            placeholder="至少 6 位"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="confirm"
            type="password"
            size="large"
            class="ink-input"
            show-password
            autocomplete="new-password"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="onSubmit">
          注 册
        </el-button>
        <p class="switch-line">
          已有账号？<a class="switch-link" @click="router.push('/login')">直接登录</a>
        </p>
      </el-form>
    </div>

    <div class="copyright">企业知识问答 · 内部系统</div>
  </div>
</template>

<script setup lang="ts">
// 注册页：与登录页同构图（左下内容 + 右上远山）。
// 注册只能创建普通用户——角色由后端写死，前端不提供角色选项。
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import SealLogo from '../components/SealLogo.vue'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const displayName = ref('')
const password = ref('')
const confirm = ref('')
const loading = ref(false)

async function onSubmit() {
  // 前端先做基础校验，减少无谓请求（后端有同样的规则兜底）
  if (!/^\w{2,20}$/.test(username.value)) {
    ElMessage.warning('用户名需为 2-20 位字母、数字、下划线或中文')
    return
  }
  if (password.value.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (password.value !== confirm.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    await auth.register(username.value, password.value, displayName.value.trim())
    ElMessage.success('注册成功，已为你登录')
    router.push('/chat')
  } catch {
    /* 错误提示由 axios 拦截器统一弹出（如"用户名已被占用"） */
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
  margin: 0 0 34px;
}
/* 标签在输入框上方；输入框无底色无边框，仅底部极细墨线 */
.login-form :deep(.el-form-item__label) {
  color: var(--ink-2);
  font-size: 13px;
  padding-bottom: 4px;
  line-height: 1.4;
}
.login-form :deep(.el-form-item) {
  margin-bottom: 22px;
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
.ink-input :deep(.el-input__inner::placeholder) {
  color: var(--ink-3);
  opacity: 0.7;
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
