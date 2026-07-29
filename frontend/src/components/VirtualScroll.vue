<template>
  <div
    ref="containerRef"
    class="virtual-scroll-container"
    :style="{ height: containerHeight + 'px', overflow: 'auto' }"
    @scroll="onScroll"
  >
    <div
      class="virtual-scroll-spacer"
      :style="{ height: totalHeight + 'px' }"
    >
      <div
        class="virtual-scroll-content"
        :style="{ transform: `translateY(${offsetY}px)` }"
      >
        <div
          v-for="item in visibleItems"
          :key="item.key || item.index"
          class="virtual-scroll-item"
          :style="item.style"
        >
          <slot :item="item" :index="item.index">
            {{ item.content }}
          </slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    required: true
  },
  itemHeight: {
    type: Number,
    default: 50
  },
  containerHeight: {
    type: Number,
    default: 400
  },
  overscan: {
    type: Number,
    default: 5
  },
  keyField: {
    type: String,
    default: 'id'
  }
})

const emit = defineEmits(['scroll', 'visible-change'])

const containerRef = ref(null)
const scrollTop = ref(0)
const visibleItems = ref([])
const totalHeight = computed(() => props.items.length * props.itemHeight)
const offsetY = ref(0)

let animationId = null
let lastScrollTop = 0

const updateVisibleItems = () => {
  if (!containerRef.value || props.items.length === 0) {
    visibleItems.value = []
    return
  }

  const startIndex = Math.max(0, Math.floor(scrollTop.value / props.itemHeight) - props.overscan)
  const endIndex = Math.min(
    props.items.length,
    Math.ceil((scrollTop.value + props.containerHeight) / props.itemHeight) + props.overscan
  )

  const newVisibleItems = []
  for (let i = startIndex; i < endIndex; i++) {
    const item = props.items[i]
    newVisibleItems.push({
      ...item,
      index: i,
      key: item[props.keyField] || i,
      style: {
        position: 'absolute',
        top: `${i * props.itemHeight}px`,
        height: `${props.itemHeight}px`,
        left: 0,
        right: 0
      }
    })
  }

  visibleItems.value = newVisibleItems
  offsetY.value = startIndex * props.itemHeight

  emit('visible-change', { startIndex, endIndex, visibleItems: newVisibleItems })
}

const onScroll = (e) => {
  const newScrollTop = e.target.scrollTop

  // ʹ�� requestAnimationFrame �Ż���������
  if (animationId) {
    cancelAnimationFrame(animationId)
  }

  animationId = requestAnimationFrame(() => {
    scrollTop.value = newScrollTop
    updateVisibleItems()
    emit('scroll', { scrollTop: newScrollTop, scrollHeight: e.target.scrollHeight, clientHeight: e.target.clientHeight })
  })
}

// ���� items �仯
watch(() => props.items, () => {
  updateVisibleItems()
}, { deep: true })

// ���� itemHeight �仯
watch(() => props.itemHeight, () => {
  updateVisibleItems()
})

// ��ʼ����
onMounted(() => {
  updateVisibleItems()
})

// ����
onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})

// ������ָ������
const scrollToIndex = (index, behavior = 'smooth') => {
  if (!containerRef.value) return

  const targetScrollTop = index * props.itemHeight
  containerRef.value.scrollTo({
    top: targetScrollTop,
    behavior
  })
}

// �������ײ�
const scrollToBottom = (behavior = 'smooth') => {
  if (!containerRef.value) return

  containerRef.value.scrollTo({
    top: totalHeight.value,
    behavior
  })
}

// ����������
const scrollToTop = (behavior = 'smooth') => {
  if (!containerRef.value) return

  containerRef.value.scrollTo({
    top: 0,
    behavior
  })
}

// ��ȡ��ǰ�ɼ���Χ
const getVisibleRange = () => {
  const startIndex = Math.max(0, Math.floor(scrollTop.value / props.itemHeight) - props.overscan)
  const endIndex = Math.min(
    props.items.length,
    Math.ceil((scrollTop.value + props.containerHeight) / props.itemHeight) + props.overscan
  )

  return { startIndex, endIndex }
}

// ��¶�����������
defineExpose({
  scrollToIndex,
  scrollToBottom,
  scrollToTop,
  getVisibleRange
})
</script>

<style scoped>
.virtual-scroll-container {
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
}

.virtual-scroll-container::-webkit-scrollbar {
  width: 6px;
}

.virtual-scroll-container::-webkit-scrollbar-track {
  background: transparent;
}

.virtual-scroll-container::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.virtual-scroll-container::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.virtual-scroll-spacer {
  position: relative;
  width: 100%;
}

.virtual-scroll-content {
  position: relative;
  width: 100%;
}

.virtual-scroll-item {
  position: absolute;
  left: 0;
  right: 0;
  box-sizing: border-box;
}
</style>
