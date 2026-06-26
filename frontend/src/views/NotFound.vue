<script setup lang="ts">
import { useRouter } from 'vue-router'
import { HomeOutline } from '@vicons/ionicons5'

const router = useRouter()
</script>

<template>
  <div class="not-found-page">
    <div class="not-found-content">
      <div class="not-found-code">404</div>
      <p class="not-found-text">页面走丢了</p>
      <n-button type="primary" size="large" @click="router.push('/')">
        <template #icon><n-icon><HomeOutline /></n-icon></template>
        回到首页
      </n-button>
    </div>
  </div>
</template>

<style scoped>
.not-found-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--app-bg, #f8f9fc);
}

.not-found-content {
  text-align: center;
}

.not-found-code {
  font-size: 120px;
  font-weight: 800;
  color: var(--app-primary, #4f46e5);
  opacity: 0.2;
  line-height: 1;
}

.not-found-text {
  font-size: 20px;
  color: var(--app-text-3, #9ca3af);
  margin: 16px 0 32px;
}
</style>
