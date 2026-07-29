<template>
  <div class="text-seg" v-html="renderedContent"></div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  content: {
    type: String,
    required: true
  }
})

// ���� marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderedContent = computed(() => {
  if (!props.content) return ''
  return marked.parse(props.content)
})
</script>

<style scoped>
.text-seg {
  line-height: 1.6;
  word-break: break-word;
}

.text-seg :deep(p) {
  margin: 0 0 8px 0;
}

.text-seg :deep(p:last-child) {
  margin-bottom: 0;
}

.text-seg :deep(code) {
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
}

.text-seg :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.text-seg :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 13px;
  line-height: 1.5;
}

.text-seg :deep(blockquote) {
  border-left: 3px solid var(--primary);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-secondary);
}

.text-seg :deep(ul), .text-seg :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.text-seg :deep(li) {
  margin: 4px 0;
}

.text-seg :deep(a) {
  color: var(--primary);
  text-decoration: none;
}

.text-seg :deep(a:hover) {
  text-decoration: underline;
}

.text-seg :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
}

.text-seg :deep(th), .text-seg :deep(td) {
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 8px 12px;
  text-align: left;
}

.text-seg :deep(th) {
  background: rgba(255, 255, 255, 0.05);
  font-weight: 600;
}

.text-seg :deep(tr:nth-child(even)) {
  background: rgba(255, 255, 255, 0.02);
}

.text-seg :deep(h1), .text-seg :deep(h2), .text-seg :deep(h3),
.text-seg :deep(h4), .text-seg :deep(h5), .text-seg :deep(h6) {
  margin: 16px 0 8px 0;
  font-weight: 600;
}

.text-seg :deep(h1) { font-size: 1.5em; }
.text-seg :deep(h2) { font-size: 1.3em; }
.text-seg :deep(h3) { font-size: 1.1em; }
</style>
