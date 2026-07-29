<template>
  <div class="skeleton-wrapper" :class="type">
    <!-- 消息骨架屏 -->
    <template v-if="type === 'message'">
      <div class="skeleton-bubble" :class="role">
        <div class="skeleton-avatar" v-if="role === 'assistant'"></div>
        <div class="skeleton-content">
          <div class="skeleton-line w80"></div>
          <div class="skeleton-line w60"></div>
          <div class="skeleton-line w40"></div>
        </div>
      </div>
    </template>

    <!-- 会话列表骨架屏 -->
    <template v-else-if="type === 'session'">
      <div class="skeleton-session" v-for="i in count" :key="i">
        <div class="skeleton-avatar-sm"></div>
        <div class="skeleton-session-info">
          <div class="skeleton-line w70"></div>
          <div class="skeleton-line w50"></div>
        </div>
      </div>
    </template>

    <!-- 卡片骨架屏 -->
    <template v-else-if="type === 'card'">
      <div class="skeleton-card" v-for="i in count" :key="i">
        <div class="skeleton-image"></div>
        <div class="skeleton-card-body">
          <div class="skeleton-line w80"></div>
          <div class="skeleton-line w60"></div>
        </div>
      </div>
    </template>

    <!-- 通用骨架屏 -->
    <template v-else>
      <div class="skeleton-line" :class="lineClass" v-for="i in count" :key="i"></div>
    </template>
  </div>
</template>

<script setup>
const props = defineProps({
  type: {
    type: String,
    default: 'line',
    validator: (val) => ['line', 'message', 'session', 'card'].includes(val)
  },
  count: {
    type: Number,
    default: 3
  },
  role: {
    type: String,
    default: 'assistant'
  },
  lineClass: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.skeleton-wrapper {
  padding: 12px;
}

/* 基础骨架线 */
.skeleton-line {
  height: 14px;
  border-radius: 6px;
  background: linear-gradient(90deg,
    rgba(255, 255, 255, 0.06) 25%,
    rgba(255, 255, 255, 0.12) 50%,
    rgba(255, 255, 255, 0.06) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease-in-out infinite;
  margin-bottom: 10px;
}

.skeleton-line:last-child {
  margin-bottom: 0;
}

/* 宽度变体 */
.skeleton-line.w40 { width: 40%; }
.skeleton-line.w50 { width: 50%; }
.skeleton-line.w60 { width: 60%; }
.skeleton-line.w70 { width: 70%; }
.skeleton-line.w80 { width: 80%; }

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 消息骨架屏 */
.skeleton-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.skeleton-bubble.user {
  flex-direction: row-reverse;
}

.skeleton-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(124, 92, 252, 0.2), rgba(124, 92, 252, 0.1));
  animation: skeleton-pulse 2s ease-in-out infinite;
}

.skeleton-content {
  flex: 1;
  max-width: 70%;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  padding: 12px;
}

.skeleton-bubble.user .skeleton-content {
  background: rgba(124, 92, 252, 0.05);
}

@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.95); }
}

/* 会话列表骨架屏 */
.skeleton-session {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.03);
}

.skeleton-avatar-sm {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(124, 92, 252, 0.2), rgba(124, 92, 252, 0.1));
  animation: skeleton-pulse 2s ease-in-out infinite;
}

.skeleton-session-info {
  flex: 1;
}

/* 卡片骨架屏 */
.skeleton-card {
  border-radius: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.03);
  margin-bottom: 12px;
}

.skeleton-image {
  width: 100%;
  height: 120px;
  background: linear-gradient(135deg, rgba(124, 92, 252, 0.1), rgba(124, 92, 252, 0.05));
  animation: skeleton-pulse 2s ease-in-out infinite;
}

.skeleton-card-body {
  padding: 12px;
}
</style>
