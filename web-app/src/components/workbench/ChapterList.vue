<template>
  <aside class="sidebar">
    <div class="sidebar-head">
      <n-button quaternary size="small" class="back-btn" @click="handleBack">
        <template #icon>
          <span class="ico-arrow">←</span>
        </template>
        书目列表
      </n-button>
      <h3 class="sidebar-title">章节</h3>
    </div>
    <n-scrollbar class="sidebar-scroll">
      <div v-if="!chapters.length" class="sidebar-empty">暂无章节大纲，可先执行「结构规划」</div>
      <n-list v-else hoverable clickable>
        <n-list-item
          v-for="ch in chapters"
          :key="ch.id"
          :class="{ 'is-active': currentChapterId === ch.id }"
          @click="handleChapterClick(ch.id)"
        >
          <n-thing :title="`第${ch.number}章`">
            <template #description>
              <div style="display: flex; flex-direction: column; gap: 4px;">
                <n-text depth="3" style="font-size: 12px;">{{ ch.title }}</n-text>
                <n-tag size="small" :type="ch.word_count > 0 ? 'success' : 'default'" round>
                  {{ ch.word_count > 0 ? '已收稿' : '未收稿' }}
                </n-tag>
              </div>
            </template>
          </n-thing>
        </n-list-item>
      </n-list>
    </n-scrollbar>
  </aside>
</template>

<script setup lang="ts">
interface Chapter {
  id: number
  number: number
  title: string
  word_count: number
}

interface ChapterListProps {
  slug: string
  chapters: Chapter[]
  currentChapterId?: number | null
}

const props = withDefaults(defineProps<ChapterListProps>(), {
  chapters: () => [],
  currentChapterId: null
})

const emit = defineEmits<{
  select: [id: number]
  back: []
}>()

const handleChapterClick = (id: number) => {
  emit('select', id)
}

const handleBack = () => {
  emit('back')
}
</script>

<style scoped>
.sidebar {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 10px;
  background: var(--app-surface);
  border-right: 1px solid var(--aitext-split-border);
}

.sidebar-head {
  margin-bottom: 10px;
}

.back-btn {
  margin-bottom: 8px;
  font-weight: 500;
}

.ico-arrow {
  font-size: 14px;
  margin-right: 2px;
}

.sidebar-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.sidebar-scroll {
  flex: 1;
  min-height: 0;
}

.sidebar-empty {
  padding: 12px;
  font-size: 13px;
  color: var(--app-muted);
  line-height: 1.5;
}

.sidebar :deep(.n-list-item) {
  border-radius: 10px;
  margin-bottom: 4px;
  transition: background var(--app-transition), transform 0.15s ease;
}

.sidebar :deep(.n-list-item:hover) {
  background: rgba(79, 70, 229, 0.06);
}

.sidebar :deep(.n-list-item.is-active) {
  background: rgba(79, 70, 229, 0.12);
  box-shadow: inset 0 0 0 1px rgba(79, 70, 229, 0.25);
}
</style>