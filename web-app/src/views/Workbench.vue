<template>
  <div class="workbench">
    <StatsTopBar :slug="slug" />

    <n-spin :show="pageLoading" class="workbench-spin" description="加载工作台…">
      <div class="workbench-inner">
        <n-split direction="horizontal" :min="0.12" :max="0.30" :default-size="0.18">
          <template #1>
            <ChapterList
              :slug="slug"
              :chapters="chapters"
              :current-chapter-id="currentChapterId"
              @select="handleChapterSelect"
              @back="goHome"
            />
          </template>

          <template #2>
            <n-split direction="horizontal" :min="0.40" :max="0.75" :default-size="0.60">
              <template #1>
                <WorkArea
                  ref="workAreaRef"
                  :slug="slug"
                  :book-title="bookTitle"
                  :chapters="chapters"
                  :current-chapter-id="currentChapterId"
                  :chapter-content="chapterContent"
                  :chapter-loading="chapterLoading"
                  @set-right-panel="setRightPanel"
                  @start-write="openWorkflowGenerate"
                  @chapter-updated="handleChapterUpdated"
                />
              </template>

              <template #2>
                <SettingsPanel
                  :slug="slug"
                  :current-panel="rightPanel"
                  :bible-key="biblePanelKey"
                  :current-chapter="currentChapter"
                />
              </template>
            </n-split>
          </template>
        </n-split>
      </div>
    </n-spin>

    <GenerateChapterWorkflowModal
      v-model:show="showWorkflowModal"
      :slug="slug"
      :chapters="chapters"
      :default-chapter-id="currentChapterId"
      @saved="onWorkflowChapterSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useWorkbench } from '../composables/useWorkbench'
import StatsTopBar from '../components/stats/StatsTopBar.vue'
import ChapterList from '../components/workbench/ChapterList.vue'
import WorkArea from '../components/workbench/WorkArea.vue'
import SettingsPanel from '../components/workbench/SettingsPanel.vue'
import GenerateChapterWorkflowModal from '../components/workbench/GenerateChapterWorkflowModal.vue'

const route = useRoute()
const message = useMessage()

const slug = route.params.slug as string
const workAreaRef = ref<InstanceType<typeof WorkArea> | null>(null)
const showWorkflowModal = ref(false)

const openWorkflowGenerate = () => {
  showWorkflowModal.value = true
}

const onWorkflowChapterSaved = async () => {
  await loadDesk()
  biblePanelKey.value += 1
}

const handleChapterUpdated = async () => {
  await loadDesk()
  biblePanelKey.value += 1
}

const {
  bookTitle,
  chapters,
  rightPanel,
  biblePanelKey,
  pageLoading,
  bookMeta,
  currentJobId,
  currentChapterId,
  chapterContent,
  chapterLoading,
  setRightPanel,
  loadDesk,
  goHome,
  goToChapter,
  handleChapterSelect,
} = useWorkbench({ slug, chatAreaRef: workAreaRef })

const currentChapter = computed(() => {
  if (!currentChapterId.value) return null
  return chapters.value.find(ch => ch.id === currentChapterId.value) || null
})

onMounted(async () => {
  try {
    await loadDesk()
  } catch {
    message.error('加载失败，请检查网络与后端是否已启动')
    bookTitle.value = slug
  } finally {
    pageLoading.value = false
  }
})
</script>

<style scoped>
.workbench {
  height: 100vh;
  min-height: 0;
  background: var(--app-page-bg, #f0f2f8);
  display: flex;
  flex-direction: column;
}

.workbench-spin {
  flex: 1;
  min-height: 0;
}

.workbench-spin :deep(.n-spin-content) {
  min-height: 100%;
  height: 100%;
}

.workbench-inner {
  height: 100%;
  min-height: 0;
}

.workbench-inner :deep(.n-split) {
  height: 100%;
}

.workbench-inner :deep(.n-split-pane-1) {
  min-height: 0;
  overflow: hidden;
}
</style>
