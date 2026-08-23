<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="logo">📚</div>
      <h1>企业知识问答</h1>
      <p class="sub">基于企业知识库的智能问答系统</p>
      <el-form @submit.prevent="onSubmit" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="username" placeholder="请输入用户名" size="large" @keyup.enter="onSubmit" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="onSubmit">
          登 录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

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
    /* interceptor shows the error */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef3ff 0%, #f7f9fc 60%);
}
.login-card {
  width: 380px;
  background: #fff;
  border-radius: 16px;
  padding: 40px 36px;
  box-shadow: 0 12px 40px rgba(47, 107, 255, 0.1);
  text-align: center;
}
.logo {
  font-size: 44px;
}
h1 {
  margin: 10px 0 4px;
  font-size: 22px;
}
.sub {
  color: var(--sub);
  font-size: 13px;
  margin-bottom: 26px;
}
.login-btn {
  width: 100%;
  margin-top: 8px;
}
</style>
