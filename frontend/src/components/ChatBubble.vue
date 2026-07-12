<template>
  <div class="bubble" :class="[msg.role, { streaming: msg.streaming }]">
    <div class="bubble-content">{{ msg.content }}</div>
  </div>
</template>

<script setup>
defineProps({ msg: Object })
</script>

<style scoped>
.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  margin: 6px 0;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.user {
  background: var(--bubble-user);
  margin-left: auto;
  border-bottom-right-radius: 4px;
}
.assistant {
  background: var(--bubble-agent);
  margin-right: auto;
  border-bottom-left-radius: 4px;
}
.streaming::after {
  content: '▊';
  animation: blink 0.8s infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>
