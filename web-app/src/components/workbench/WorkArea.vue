<template>
  <div class="work-area">
    <header class="work-header">
      <div class="work-title-wrap">
        <h2 class="work-title">{{ bookTitle || slug }}</h2>
        <n-text depth="3" class="work-sub">{{ slug }}</n-text>
      </div>
      <n-space :size="12" align="center" wrap class="work-header-actions">
        <n-button-group size="small">
          <n-button :type="rightPanel === 'bible' ? 'primary' : 'default'" @click="setRightPanel('bible')">
            设定
          </n-button>
          <n-button :type="rightPanel === 'knowledge' ? 'primary' : 'default'" @click="setRightPanel('knowledge')">
            叙事与关系
          </n-button>
        </n-button-group>
      </n-space>
    </header>

    <n-tabs v-model:value="activeTab" type="line" animated class="work-tabs">
      <!-- 工作台 Tab -->
      <n-tab-pane name="workbench" tab="工作台">
        <div class="tab-content">
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
                :autosize="{ minRows: 20 }"
                @update:value="handleContentChange"
              />
            </div>

            <div class="editor-footer">
              <n-space :size="8" align="center">
                <n-text depth="3">字数: {{ wordCount }}</n-text>
                <n-divider vertical />
                <n-button size="tiny" @click="handleGenerateChapter" :loading="generating">
                  生成本章
                </n-button>
                <n-button size="tiny" @click="handleReviewChapter" :loading="reviewing" :disabled="currentChapter.word_count === 0">
                  AI审稿
                </n-button>
              </n-space>
            </div>

            <!-- 审稿结果展示区域 -->
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

          <n-empty v-else description="请从左侧选择章节" style="margin-top: 100px" />
        </div>
      </n-tab-pane>

      <!-- 撰稿 Tab -->
      <n-tab-pane name="write" tab="撰稿">
        <div class="tab-content">
          <n-space vertical :size="20">
            <!-- 结构规划 -->
            <n-card title="结构规划" size="small" :bordered="false">
              <n-space vertical :size="16">
                <n-text depth="3">
                  首次生成适用于尚无圣经与大纲；「再规划」会结合已完成章节信息，修订 Bible 与分章大纲。
                </n-text>
                <n-radio-group v-model:value="planMode" size="small">
                  <n-space vertical :size="8">
                    <n-radio value="initial">首次生成圣经与分章大纲</n-radio>
                    <n-radio value="revise">基于进度再规划</n-radio>
                  </n-space>
                </n-radio-group>
                <n-checkbox v-model:checked="planDryRun" size="small">
                  预演（dry-run，不调用模型）
                </n-checkbox>
                <n-button type="primary" @click="handlePlan" :loading="planning" size="small">
                  开始规划
                </n-button>
              </n-space>
            </n-card>

            <!-- 单章撰稿 -->
            <n-card title="单章撰稿" size="small" :bordered="false">
              <n-space vertical :size="16">
                <n-text depth="3">
                  为指定章节生成内容，支持流式输出。
                </n-text>
                <n-form-item label="章节号" label-placement="left" label-width="80">
                  <n-input-number v-model:value="singleChapter" :min="1" size="small" style="width: 120px" />
                </n-form-item>
                <n-form-item label="大纲" label-placement="left" label-width="80">
                  <n-input
                    v-model:value="singleOutline"
                    type="textarea"
                    placeholder="输入章节大纲..."
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    size="small"
                  />
                </n-form-item>
                <n-button
                  type="primary"
                  @click="handleSingleWrite"
                  :loading="singleWriting"
                  :disabled="singleWriting"
                  size="small"
                >
                  {{ singleWriting ? '生成中...' : '开始生成' }}
                </n-button>
              </n-space>
            </n-card>

            <!-- 托管连写 -->
            <n-card title="托管连写" size="small" :bordered="false">
              <n-space vertical :size="16">
                <n-text depth="3">
                  自动生成多章，无需人工干预。生成过程会实时显示在下方。
                </n-text>
                <n-space :size="12">
                  <n-form-item label="起始章节" label-placement="left" label-width="80">
                    <n-input-number v-model:value="hostedFrom" :min="1" size="small" style="width: 100px" />
                  </n-form-item>
                  <n-form-item label="结束章节" label-placement="left" label-width="80">
                    <n-input-number v-model:value="hostedTo" :min="1" size="small" style="width: 100px" />
                  </n-form-item>
                </n-space>
                <n-space :size="12">
                  <n-checkbox v-model:value="hostedAutoSave" size="small">自动保存</n-checkbox>
                  <n-checkbox v-model:value="hostedAutoOutline" size="small">自动生成大纲</n-checkbox>
                </n-space>
                <n-button
                  type="primary"
                  @click="handleStartHosted"
                  :loading="hostedRunning"
                  :disabled="hostedRunning"
                  size="small"
                >
                  {{ hostedRunning ? '生成中...' : '开始托管连写' }}
                </n-button>
              </n-space>
            </n-card>

            <!-- 实时输出区域 -->
            <n-card v-if="outputVisible" title="生成输出" size="small" :bordered="false">
              <template #header-extra>
                <n-button size="tiny" @click="clearOutput">清空</n-button>
              </template>
              <n-scrollbar style="max-height: 400px">
                <div class="output-area">
                  <pre>{{ outputText }}</pre>
                </div>
              </n-scrollbar>
            </n-card>
          </n-space>
        </div>
      </n-tab-pane>
    </n-tabs>
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
const activeTab = ref('workbench')

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

  generating.value = true
  outputVisible.value = true
  outputText.value = ''

  // 切换到撰稿 tab 显示输出
  activeTab.value = 'write'

  try {
    await workflowApi.consumeGenerateChapterStream(
      props.slug,
      {
        chapter_number: currentChapter.value.id,
        outline: '根据大纲生成'
      },
      {
        onEvent: (event) => {
          if (event.type === 'phase') {
            outputText.value += `[阶段] ${event.phase}\n`
          } else if (event.type === 'chunk') {
            outputText.value += event.text
          } else if (event.type === 'done') {
            outputText.value += '\n\n--- 生成完成 ---\n'
            chapterContent.value = event.content
            originalContent.value = event.content
            message.success('章节生成完成')
            emit('chapterUpdated')
          } else if (event.type === 'error') {
            outputText.value += `\n\n[错误] ${event.message}\n`
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

// 规划
const planMode = ref<'initial' | 'revise'>('initial')
const planDryRun = ref(false)
const planning = ref(false)

// 单章撰稿
const singleChapter = ref(1)
const singleOutline = ref('')
const singleWriting = ref(false)

// 托管
const hostedFrom = ref(1)
const hostedTo = ref(5)
const hostedAutoSave = ref(true)
const hostedAutoOutline = ref(true)
const hostedRunning = ref(false)

// 输出
const outputVisible = ref(false)
const outputText = ref('')

const setRightPanel = (panel: string) => {
  rightPanel.value = panel
  emit('setRightPanel', panel)
}

const handlePlan = async () => {
  planning.value = true
  try {
    const result = await workflowApi.planNovel(props.slug, planMode.value, planDryRun.value)
    if (result.success) {
      message.success(result.message)
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '规划失败')
  } finally {
    planning.value = false
  }
}

const handleSingleWrite = async () => {
  if (!singleOutline.value.trim()) {
    message.warning('请输入章节大纲')
    return
  }

  singleWriting.value = true
  outputVisible.value = true
  outputText.value = ''

  try {
    await workflowApi.consumeGenerateChapterStream(
      props.slug,
      {
        chapter_number: singleChapter.value,
        outline: singleOutline.value
      },
      {
        onEvent: (event) => {
          if (event.type === 'phase') {
            outputText.value += `[阶段] ${event.phase}\n`
          } else if (event.type === 'chunk') {
            outputText.value += event.text
          } else if (event.type === 'done') {
            outputText.value += '\n\n--- 生成完成 ---\n'
            message.success('章节生成完成')
          } else if (event.type === 'error') {
            outputText.value += `\n\n[错误] ${event.message}\n`
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
    singleWriting.value = false
  }
}

const startWrite = () => {
  emit('startWrite')
}

const handleStartHosted = async () => {
  hostedRunning.value = true
  outputVisible.value = true
  outputText.value = ''

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
          outputText.value += JSON.stringify(event, null, 2) + '\n\n'
        },
        onError: (err) => {
          message.error(`托管连写失败: ${err}`)
          hostedRunning.value = false
        }
      }
    )
    message.success('托管连写完成')
  } catch (error) {
    message.error('托管连写失败')
  } finally {
    hostedRunning.value = false
  }
}

const clearOutput = () => {
  outputText.value = ''
  outputVisible.value = false
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

.work-tabs {
  flex: 1;
  min-height: 0;
}

.work-tabs :deep(.n-tabs-nav) {
  padding-left: 20px;
}

.work-tabs :deep(.n-tabs-tab) {
  padding: 12px 24px;
  font-size: 14px;
  font-weight: 500;
}

.work-tabs :deep(.n-tabs-pane-wrapper) {
  height: 100%;
}

.tab-content {
  height: 100%;
  padding: 20px;
  overflow-y: auto;
  max-width: 800px;
  margin: 0 auto;
}

.output-area {
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--text-color-2);
}

.work-tabs :deep(.n-card) {
  background: var(--card-color);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.work-tabs :deep(.n-card__header) {
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
}

.work-tabs :deep(.n-card__content) {
  padding: 16px;
}

.work-tabs :deep(.n-form-item) {
  margin-bottom: 0;
}

.work-tabs :deep(.n-button) {
  font-weight: 500;
}

.chapter-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
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
