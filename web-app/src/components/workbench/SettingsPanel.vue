<template>
  <div class="right-panel">
    <BiblePanel v-if="currentPanel === 'bible'" :key="bibleKey" :slug="slug" />
    <KnowledgePanel v-else :slug="slug" />

    <!-- Chapter Info Card -->
    <div v-if="currentChapter" class="chapter-info-card">
      <n-card size="small" :bordered="false" title="当前章节">
        <n-space vertical :size="12">
          <div class="info-row">
            <n-text depth="3">章节号:</n-text>
            <n-text strong>第{{ currentChapter.number }}章</n-text>
          </div>
          <div class="info-row">
            <n-text depth="3">标题:</n-text>
            <n-text>{{ currentChapter.title || '未设置' }}</n-text>
          </div>
          <div class="info-row">
            <n-text depth="3">字数:</n-text>
            <n-tag :type="currentChapter.word_count > 0 ? 'success' : 'default'" size="small">
              {{ currentChapter.word_count }} 字
            </n-tag>
          </div>
          <div class="info-row">
            <n-text depth="3">状态:</n-text>
            <n-tag :type="currentChapter.word_count > 0 ? 'success' : 'default'" size="small" round>
              {{ currentChapter.word_count > 0 ? '已收稿' : '未收稿' }}
            </n-tag>
          </div>
        </n-space>
      </n-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import BiblePanel from '../BiblePanel.vue'
import KnowledgePanel from '../KnowledgePanel.vue'

interface Chapter {
  id: number
  number: number
  title: string
  word_count: number
}

interface Props {
  slug: string
  /** 与 Workbench 的 `current-panel` 对应 */
  currentPanel?: 'bible' | 'knowledge'
  bibleKey?: number
  currentChapter?: Chapter | null
}

withDefaults(defineProps<Props>(), {
  currentPanel: 'knowledge',
  bibleKey: 0,
  currentChapter: null,
})
</script>

<style scoped>
.right-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--aitext-panel-muted);
  border-left: 1px solid var(--aitext-split-border);
}

.chapter-info-card {
  padding: 12px;
  border-top: 1px solid var(--aitext-split-border);
  background: var(--app-surface);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
</style>