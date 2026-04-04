<template>
  <div class="work-area">
    <header class="work-header">
      <div class="work-title-wrap">
        <h2 class="work-title">{{ bookTitle || slug }}</h2>
        <n-text depth="3" class="work-sub">{{ slug }}</n-text>
      </div>
      <n-space :size="12" align="center" wrap class="work-header-actions">
        <n-button type="primary" size="small" @click="openHostedWriteModal">
          托管连写
        </n-button>
      </n-space>
    </header>

    <div class="work-main">
      <div v-if="currentChapter" class="chapter-editor">
        <div class="editor-header">
          <div class="editor-title">
            <h3>{{ currentChapter.title || `第${currentChapter.number}章` }}</h3>
            <n-tag size="small" :type="currentChapter.word_count > 0 ? 'success' : 'default'" round>
              {{ currentChapter.word_count > 0 ? '已收稿' : '未收稿' }}
            </n-tag>
          </div>
          <n-space :size="8">
            <n-button size="small" @click="handleReload" :disabled="loading">
              重新加载
            </n-button>
            <n-button size="small" type="primary" @click="handleSave" :disabled="!hasChanges" :loading="saving">
              保存
            </n-button>
          </n-space>
        </div>

        <div class="editor-body">
          <n-input
            v-model:value="chapterContent"
            type="textarea"
            placeholder="章节内容..."
            :autosize="{ minRows: 22 }"
            @update:value="handleContentChange"
          />
        </div>

        <div class="editor-footer">
          <n-space :size="8" align="center" justify="space-between" style="width: 100%">
            <n-text depth="3">字数: {{ wordCount }}</n-text>
            <n-space :size="8">
              <n-button size="small" secondary @click="handleGenerateChapter" :loading="generating">
                AI 生成本章
              </n-button>
              <n-button size="small" @click="handleReviewChapter" :loading="reviewing" :disabled="currentChapter.word_count === 0">
                AI 审稿
              </n-button>
            </n-space>
          </n-space>
        </div>

        <div v-if="reviewResult" class="review-result">
          <n-card title="审稿结果" size="small" :bordered="false">
            <template #header-extra>
              <n-button size="tiny" text @click="reviewResult = null">
                关闭
              </n-button>
            </template>
            <n-space vertical :size="12">
              <div class="review-score">
                <n-text strong>评分: </n-text>
                <n-tag :type="reviewResult.score >= 80 ? 'success' : reviewResult.score >= 60 ? 'warning' : 'error'" size="large">
                  {{ reviewResult.score }}/100
                </n-tag>
              </div>
              <n-divider style="margin: 8px 0" />
              <div v-if="reviewResult.suggestions && reviewResult.suggestions.length > 0">
                <n-text strong>改进建议:</n-text>
                <n-list bordered style="margin-top: 8px">
                  <n-list-item v-for="(suggestion, index) in reviewResult.suggestions" :key="index">
                    <n-thing>
                      <template #header>
                        <n-text>{{ index + 1 }}. {{ suggestion }}</n-text>
                      </template>
                    </n-thing>
                  </n-list-item>
                </n-list>
              </div>
              <div v-else>
                <n-text depth="3">暂无改进建议</n-text>
              </div>
            </n-space>
          </n-card>
        </div>
      </div>

      <n-empty v-else description="请从左侧选择章节，或使用顶部「托管连写」批量生成多章" class="work-empty" />
    </div>

    <!-- 托管连写弹窗 -->
    <n-modal
      v-model:show="showHostedModal"
      preset="card"
      title="托管连写"
      style="width: min(820px, 96vw); max-height: min(92vh, 900px)"
      :segmented="{ content: true, footer: 'soft' }"
      :mask-closable="!hostedRunning"
    >
      <template #header-extra>
        <n-text depth="3" style="font-size: 12px">自动生成多章，实时显示进度</n-text>
      </template>

      <n-scrollbar style="max-height: min(78vh, 760px)">
        <n-space vertical :size="20">
          <n-alert type="info" :show-icon="true">
            全自动区间生成：每章先用 AI 生成大纲，再流式生成正文。请确保章节已在书中存在，否则无法自动保存。
          </n-alert>

          <n-card title="配置" size="small" :bordered="false">
            <n-space vertical :size="16">
              <n-form-item label="章节范围" label-placement="left" label-width="80">
                <n-space :size="12" align="center">
                  <n-input-number v-model:value="hostedFrom" :min="1" :disabled="hostedRunning" placeholder="起始章" style="width: 100px" />
                  <n-text depth="3">至</n-text>
                  <n-input-number v-model:value="hostedTo" :min="1" :disabled="hostedRunning" placeholder="结束章" style="width: 100px" />
                </n-space>
              </n-form-item>

              <n-space vertical :size="8">
                <n-checkbox v-model:checked="hostedAutoOutline" :disabled="hostedRunning" size="small">
                  自动生成大纲（使用 AI 生成每章要点，推荐）
                </n-checkbox>
                <n-checkbox v-model:checked="hostedAutoSave" :disabled="hostedRunning" size="small">
                  自动保存（每章生成后自动写入章节正文）
                </n-checkbox>
              </n-space>

              <n-button
                type="primary"
                @click="handleStartHosted"
                :loading="hostedRunning"
                :disabled="hostedRunning"
                size="medium"
                block
              >
                {{ hostedRunning ? '生成中...' : '开始托管连写' }}
              </n-button>
            </n-space>
          </n-card>

          <n-card v-if="hostedRunning || hostedLog" title="生成日志" size="small" :bordered="false">
            <template #header-extra>
              <n-button size="tiny" @click="hostedLog = ''" :disabled="hostedRunning">清空</n-button>
            </template>
            <n-scrollbar style="max-height: 400px">
              <div class="output-area">
                <pre>{{ hostedLog }}</pre>
              </div>
            </n-scrollbar>
          </n-card>
        </n-space>
      </n-scrollbar>

      <template #footer>
        <n-space justify="end">
          <n-button @click="showHostedModal = false" :disabled="hostedRunning">关闭</n-button>
          <n-button v-if="hostedRunning" secondary @click="stopHosted">停止</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- AI 生成本章弹窗 -->
    <n-modal
      v-model:show="showGenerateModal"
      preset="card"
      title="AI 生成本章"
      style="width: min(820px, 96vw); max-height: min(92vh, 900px)"
      :segmented="{ content: true, footer: 'soft' }"
      :mask-closable="!generating"
    >
      <template #header-extra>
        <n-text depth="3" style="font-size: 12px">流式生成，实时显示</n-text>
      </template>

      <n-scrollbar style="max-height: min(78vh, 760px)">
        <n-space vertical :size="20">
          <n-alert type="info" :show-icon="true">
            为当前章节生成内容，支持自定义大纲。生成完成后可编辑并保存。
          </n-alert>

          <n-card title="配置" size="small" :bordered="false">
            <n-space vertical :size="16">
              <n-form-item label="章节" label-placement="left" label-width="80">
                <n-text>第 {{ currentChapter?.number }} 章 - {{ currentChapter?.title }}</n-text>
              </n-form-item>

              <n-form-item label="大纲" label-placement="left" label-width="80">
                <n-input
                  v-model:value="generateOutline"
                  type="textarea"
                  placeholder="输入章节大纲（可选，留空则使用默认大纲）"
                  :autosize="{ minRows: 3, maxRows: 6 }"
                  :disabled="generating"
                />
              </n-form-item>

              <n-button
                type="primary"
                @click="handleStartGenerate"
                :loading="generating"
                :disabled="generating"
                size="medium"
                block
              >
                {{ generating ? '生成中...' : '开始生成' }}
              </n-button>
            </n-space>
          </n-card>

          <n-card v-if="generating || generatedContent" title="生成内容" size="small" :bordered="false">
            <template #header-extra>
              <n-space :size="8">
                <n-button v-if="generatedContent && !generating" size="tiny" type="primary" @click="handleSaveGenerated" :loading="saving">
                  保存到章节
                </n-button>
                <n-button size="tiny" @click="generatedContent = ''" :disabled="generating">清空</n-button>
              </n-space>
            </template>
            <n-scrollbar style="max-height: 500px">
              <n-input
                v-model:value="generatedContent"
                type="textarea"
                :autosize="{ minRows: 15, maxRows: 30 }"
                :readonly="generating"
                placeholder="生成的内容将在此显示..."
              />
            </n-scrollbar>
          </n-card>
        </n-space>
      </n-scrollbar>

      <template #footer>
        <n-space justify="end">
          <n-button @click="showGenerateModal = false" :disabled="generating">关闭</n-button>
          <n-button v-if="generating" secondary @click="stopGenerate">停止</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { workflowApi, consumeHostedWriteStream } from '../../api/workflow'
import { bookApi } from '../../api/book'

interface Chapter {
  id: number
  number: number
  title: string
  word_count: number
  content?: string
}

interface WorkAreaProps {
  slug: string
  bookTitle?: string
  chapters: Chapter[]
  currentChapterId?: number | null
  chapterContent?: string
  chapterLoading?: boolean
}

const props = withDefaults(defineProps<WorkAreaProps>(), {
  chapters: () => [],
  currentChapterId: null,
  chapterContent: '',
  chapterLoading: false
})

const emit = defineEmits<{
  setRightPanel: [panel: string]
  startWrite: []
  chapterUpdated: []
}>()

const message = useMessage()

const rightPanel = ref('bible')
const showHostedModal = ref(false)
const showGenerateModal = ref(false)
const generateOutline = ref('')
const generatedContent = ref('')

const openHostedWriteModal = () => {
  showHostedModal.value = true
}

// 章节编辑
const chapterContent = ref('')
const originalContent = ref('')
const loading = computed(() => props.chapterLoading)
const saving = ref(false)
const generating = ref(false)
const reviewing = ref(false)
const reviewResult = ref<{ score: number; suggestions: string[] } | null>(null)

const currentChapter = computed(() => {
  if (!props.currentChapterId) return null
  return props.chapters.find(ch => ch.id === props.currentChapterId) || null
})

const hasChanges = computed(() => {
  return chapterContent.value !== originalContent.value
})

const wordCount = computed(() => {
  return chapterContent.value.length
})

// 监听传入的章节内容变化
watch(() => props.chapterContent, (newContent) => {
  chapterContent.value = newContent
  originalContent.value = newContent
}, { immediate: true })

const handleContentChange = () => {
  // 内容变化
}

const handleSave = async () => {
  if (!currentChapter.value) return

  saving.value = true
  try {
    await bookApi.updateChapter(props.slug, currentChapter.value.id, { content: chapterContent.value })
    originalContent.value = chapterContent.value
    message.success('保存成功')
    emit('chapterUpdated')
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleReload = async () => {
  if (!props.currentChapterId) return
  // Trigger reload from parent composable
  message.info('已重新加载')
}

const handleGenerateChapter = async () => {
  if (!currentChapter.value) return

  generateOutline.value = `第${currentChapter.value.number}章：${currentChapter.value.title || ''}

承接前情，推进主线与人物节拍；保持人设与叙事节奏一致。`
  generatedContent.value = ''
  showGenerateModal.value = true
}

const handleStartGenerate = async () => {
  if (!currentChapter.value) return

  generating.value = true
  generatedContent.value = ''

  try {
    await workflowApi.consumeGenerateChapterStream(
      props.slug,
      {
        chapter_number: currentChapter.value.number,
        outline: generateOutline.value || `第${currentChapter.value.number}章：承接前情，推进主线`
      },
      {
        onEvent: (event) => {
          if (event.type === 'phase') {
            generatedContent.value += `[阶段: ${event.phase}]\n`
          } else if (event.type === 'chunk') {
            generatedContent.value += event.text
          } else if (event.type === 'done') {
            generatedContent.value = event.content
            message.success('章节生成完成')
          } else if (event.type === 'error') {
            generatedContent.value += `\n\n[错误] ${event.message}\n`
            message.error(`生成失败: ${event.message}`)
          }
        },
        onError: (err) => {
          message.error(`生成失败: ${err}`)
        }
      }
    )
  } catch (error) {
    message.error('生成失败')
  } finally {
    generating.value = false
  }
}

const handleSaveGenerated = async () => {
  if (!currentChapter.value || !generatedContent.value) return

  saving.value = true
  try {
    await bookApi.updateChapter(props.slug, currentChapter.value.id, { content: generatedContent.value })
    chapterContent.value = generatedContent.value
    originalContent.value = generatedContent.value
    message.success('保存成功')
    emit('chapterUpdated')
    showGenerateModal.value = false
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const stopGenerate = () => {
  generating.value = false
  message.info('已停止生成')
}

const handleReviewChapter = async () => {
  if (!currentChapter.value) return

  reviewing.value = true
  try {
    const result = await workflowApi.reviewChapter(props.slug, currentChapter.value.id)
    reviewResult.value = {
      score: result.score,
      suggestions: result.suggestions || []
    }
    message.success(`审稿完成，评分: ${result.score}/100`)
  } catch (error: any) {
    if (error.response?.status === 501) {
      message.warning('审稿功能开发中')
    } else {
      message.error('审稿失败')
    }
  } finally {
    reviewing.value = false
  }
}

// 托管连写
const hostedFrom = ref(1)
const hostedTo = ref(5)
const hostedAutoSave = ref(true)
const hostedAutoOutline = ref(true)
const hostedRunning = ref(false)
const hostedLog = ref('')

const setRightPanel = (panel: string) => {
  rightPanel.value = panel
  emit('setRightPanel', panel)
}

const handleStartHosted = async () => {
  hostedRunning.value = true
  hostedLog.value = ''

  try {
    await consumeHostedWriteStream(
      props.slug,
      {
        from_chapter: hostedFrom.value,
        to_chapter: hostedTo.value,
        auto_save: hostedAutoSave.value,
        auto_outline: hostedAutoOutline.value
      },
      {
        onEvent: (event) => {
          if (event.type === 'session') {
            hostedLog.value += `[会话开始] 章节 ${event.from_chapter}-${event.to_chapter}，共 ${event.total} 章\n\n`
          } else if (event.type === 'chapter_start') {
            hostedLog.value += `\n[章节 ${event.chapter}] 开始生成 (${event.index}/${event.total})\n`
          } else if (event.type === 'outline') {
            hostedLog.value += `[大纲] ${event.text}\n\n`
          } else if (event.type === 'phase') {
            hostedLog.value += `[阶段: ${event.phase}]\n`
          } else if (event.type === 'chunk') {
            // 不显示每个 chunk，避免日志过长
          } else if (event.type === 'done') {
            hostedLog.value += `[完成] 章节 ${event.chapter} 生成完成，${event.content?.length || 0} 字符\n`
          } else if (event.type === 'saved') {
            if (event.ok) {
              hostedLog.value += `[保存] 章节 ${event.chapter} 已保存${event.created ? '（新建）' : ''}\n`
            } else {
              hostedLog.value += `[保存失败] 章节 ${event.chapter}: ${event.message}\n`
            }
          } else if (event.type === 'session_done') {
            hostedLog.value += `\n[会话完成] 所有章节生成完毕\n`
            message.success('托管连写完成')
            emit('chapterUpdated')
          } else if (event.type === 'error') {
            hostedLog.value += `\n[错误] ${event.message}\n`
            message.error(`生成失败: ${event.message}`)
          }
        },
        onError: (err) => {
          hostedLog.value += `\n[连接错误] ${err}\n`
          message.error(`托管连写失败: ${err}`)
        }
      }
    )
  } catch (error) {
    message.error('托管连写失败')
  } finally {
    hostedRunning.value = false
  }
}

const stopHosted = () => {
  hostedRunning.value = false
  message.info('已停止托管连写')
}
</script>

<style scoped>
.work-area {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--app-surface);
}

.work-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--aitext-split-border);
}

.work-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.work-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.work-sub {
  font-size: 13px;
}

.work-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 16px 20px 20px;
  overflow: hidden;
}

.work-empty {
  margin-top: 80px;
}

.write-modal-body {
  padding-right: 6px;
}

.output-area {
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--text-color-2);
}

.write-modal-body :deep(.n-card) {
  background: var(--card-color);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.write-modal-body :deep(.n-card__header) {
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
}

.write-modal-body :deep(.n-card__content) {
  padding: 16px;
}

.write-modal-body :deep(.n-form-item) {
  margin-bottom: 0;
}

.chapter-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.editor-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.editor-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.editor-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.editor-body :deep(.n-input) {
  height: 100%;
}

.editor-body :deep(.n-input__textarea-el) {
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.8;
}

.editor-footer {
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}
</style>
