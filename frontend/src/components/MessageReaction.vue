<template>
  <div class="message-reactions" v-if="reactions.length > 0 || showAdd">
    <div class="reaction-list">
      <button
        v-for="reaction in reactions"
        :key="reaction.emoji"
        class="reaction-badge"
        :class="{ active: reaction.userReacted }"
        @click="toggleReaction(reaction.emoji)"
      >
        <span class="reaction-emoji">{{ reaction.emoji }}</span>
        <span class="reaction-count" v-if="reaction.count > 1">{{ reaction.count }}</span>
      </button>

      <button
        v-if="showAdd"
        class="reaction-add"
        @click="showPicker = !showPicker"
      >
        +
      </button>
    </div>

    <div v-if="showPicker" class="reaction-picker">
      <button
        v-for="emoji in quickEmojis"
        :key="emoji"
        class="emoji-btn"
        @click="addReaction(emoji)"
      >
        {{ emoji }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  messageId: {
    type: String,
    required: true
  },
  initialReactions: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['reaction'])

const reactions = ref([...props.initialReactions])
const showPicker = ref(false)
const showAdd = ref(true)

const quickEmojis = ['👍', '❤️', '😊', '🎉', '🤔', '👀', '🔥', '💯']

function toggleReaction(emoji) {
  const index = reactions.value.findIndex(r => r.emoji === emoji)
  if (index >= 0) {
    if (reactions.value[index].userReacted) {
      reactions.value[index].count--
      reactions.value[index].userReacted = false
      if (reactions.value[index].count <= 0) {
        reactions.value.splice(index, 1)
      }
    } else {
      reactions.value[index].count++
      reactions.value[index].userReacted = true
    }
  }
  emit('reaction', { messageId: props.messageId, emoji })
}

function addReaction(emoji) {
  const existing = reactions.value.find(r => r.emoji === emoji)
  if (existing) {
    existing.count++
    existing.userReacted = true
  } else {
    reactions.value.push({
      emoji,
      count: 1,
      userReacted: true
    })
  }
  showPicker.value = false
  emit('reaction', { messageId: props.messageId, emoji })
}
</script>

<style scoped>
.message-reactions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.reaction-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.reaction-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.reaction-badge:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}

.reaction-badge.active {
  background: rgba(124, 92, 252, 0.2);
  border-color: var(--primary);
}

.reaction-emoji {
  font-size: 14px;
}

.reaction-count {
  font-size: 10px;
  color: var(--text-secondary);
}

.reaction-add {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px dashed rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.reaction-add:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.3);
  color: var(--text-primary);
}

.reaction-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px;
  background: rgba(20, 20, 40, 0.9);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  margin-top: 4px;
}

.emoji-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 18px;
  transition: all 0.2s;
}

.emoji-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: scale(1.2);
}
</style>
