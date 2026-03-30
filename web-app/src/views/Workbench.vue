<template>
  <div class="workbench">
    <n-spin :show="pageLoading" class="workbench-spin" description="加载工作台…">
      <div class="workbench-inner">
        <n-split direction="horizontal" :min="0.14" :max="0.42" :default-size="0.22">
          <template #1>
            <aside class="sidebar">
              <div class="sidebar-head">
                <n-button quaternary size="small" class="back-btn" @click="goHome">
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
                    @click="goToChapter(ch.id)"
                  >
                    <n-thing :title="`第${ch.id}章 ${ch.title || ''}`">
                      <template #description>
                        <n-tag size="small" :type="ch.has_file ? 'success' : 'default'" round>
                          {{ ch.has_file ? '已收稿' : '未收稿' }}
                        </n-tag>
                      </template>
                    </n-thing>
                  </n-list-item>
                </n-list>
              </n-scrollbar>
            </aside>
          </template>

          <template #2>
            <n-split direction="horizontal" :min="0.28" :max="0.72" :default-size="0.55">
              <template #1>
                <div class="chat-area">
                  <header class="chat-header">
                    <div class="chat-title-wrap">
                      <h2 class="chat-title">{{ bookTitle || slug }}</h2>
                      <n-text depth="3" class="chat-sub">{{ slug }}</n-text>
                    </div>
                    <n-space :size="12" align="center" wrap class="chat-header-actions">
                      <n-button-group size="small">
                        <n-button :type="rightPanel === 'bible' ? 'primary' : 'default'" @click="setRightPanel('bible')">
                          设定
                        </n-button>
                        <n-button :type="rightPanel === 'knowledge' ? 'primary' : 'default'" @click="setRightPanel('knowledge')">
                          叙事与关系
                        </n-button>
                      </n-button-group>
                      <n-divider vertical style="height: 22px; margin: 0" />
                      <n-space :size="8" align="center" wrap>
                        <n-button size="small" secondary @click="openPlanModal">结构规划</n-button>
                        <n-button size="small" type="primary" @click="startWrite">撰稿</n-button>
                      </n-space>
                    </n-space>
                  </header>

                  <n-scrollbar ref="messageScrollRef" class="chat-messages">
                    <div class="chat-messages-pad">
                      <div
                        v-for="msg in messages"
                        :key="msg.id"
                        class="msg-row"
                        :class="msg.role"
                      >
                        <div class="msg-bubble">
                          <div class="msg-meta">
                            <n-tag size="small" round :type="getRoleType(msg.role)">
                              {{ getRoleLabel(msg.role, msg.meta) }}
                            </n-tag>
                            <span class="msg-time">{{ formatTime(msg.ts) }}</span>
                          </div>
                          <div
                            v-if="msg.role === 'assistant' && msg.meta?.tools?.length"
                            class="msg-tools"
                          >
                            <span class="msg-tools-title">工具调用</span>
                            <div
                              v-for="(t, ti) in msg.meta.tools"
                              :key="ti"
                              class="msg-tool-line"
                            >
                              <n-tag size="tiny" round :type="t.ok ? 'success' : 'error'" :bordered="false">
                                {{ t.name }}
                              </n-tag>
                              <span class="msg-tool-detail">{{ t.detail }}</span>
                            </div>
                          </div>
                          <div class="markdown-body md-body msg-md" v-html="renderMarkdown(msg.content)" />
                        </div>
                      </div>

                      <div v-if="streamActive" class="msg-row assistant stream-live">
                        <div class="msg-bubble stream-live-bubble">
                          <div class="msg-meta">
                            <n-tag size="small" round type="info">助手 · 生成中</n-tag>
                          </div>
                          <div v-if="streamTools.length" class="msg-tools stream-thinking">
                            <span class="msg-tools-title">工具步骤（实时）</span>
                            <div
                              v-for="(t, ti) in streamTools"
                              :key="ti"
                              class="msg-tool-line"
                            >
                              <n-tag size="tiny" round :type="t.ok ? 'success' : 'error'" :bordered="false">
                                {{ t.name }}
                              </n-tag>
                              <span class="msg-tool-detail">{{ t.detail }}</span>
                            </div>
                          </div>
                          <div
                            class="markdown-body md-body msg-md stream-md"
                            v-html="renderMarkdown(streamText)"
                          />
                        </div>
                      </div>
                    </div>
                  </n-scrollbar>

                  <div class="composer">
                    <div class="composer-toolbar">
                      <n-segmented
                        v-model:value="historyMode"
                        size="small"
                        :options="historySegmentOptions"
                      />
                      <n-space :size="6" align="center" wrap>
                        <n-select
                          v-model:value="chapterPick"
                          size="tiny"
                          class="ch-pick-select"
                          :options="chapterSelectOptions"
                          placeholder="章"
                        />
                        <n-checkbox v-model:checked="clearBeforeSend" size="small" class="clear-before-check">
                          本条发送前清空对话
                        </n-checkbox>
                        <n-checkbox v-model:checked="useStreamMode" size="small">流式输出</n-checkbox>
                        <n-checkbox v-model:checked="useStreamDraft" size="small">流式撰稿区</n-checkbox>
                        <n-dropdown trigger="click" :options="clearMenuOptions" @select="onClearMenu">
                          <n-button size="tiny" quaternary>清空上下文</n-button>
                        </n-dropdown>
                      </n-space>
                    </div>
                    <n-space :size="6" wrap class="quick-prompts">
                      <n-button size="tiny" tertiary @click="fillQuick('chapter')">本章撰稿</n-button>
                      <n-button size="tiny" tertiary @click="fillQuick('batch')">批量章摘要</n-button>
                      <n-button size="tiny" tertiary @click="fillQuick('check')">梗概对齐检查</n-button>
                    </n-space>
                    <n-text depth="3" class="aitext-composer-hint">
                      {{
                        historyMode === 'fresh'
                          ? '仅本轮：不带此前多轮对话，仍含全书设定/梗概/叙事注入。Enter 发送；Ctrl+Enter 换行；Shift+Enter 换行。'
                          : '带历史：多轮对话参与上下文。开启「流式输出」时工具步骤会像思考过程一样逐条出现，正文分块显示；可开「流式撰稿区」同步到大编辑框。Enter 发送；Ctrl+Enter 换行；Shift+Enter 换行。'
                      }}
                    </n-text>
                    <n-input
                      v-model:value="inputMessage"
                      type="textarea"
                      :rows="3"
                      placeholder="输入编务指令，或点上方快捷话术…"
                      :disabled="sending"
                      class="composer-input"
                      @keydown.enter="onComposerKeydown"
                    />
                    <div class="composer-actions">
                      <n-button v-if="!sending" type="primary" round @click="sendMessage">发送</n-button>
                      <n-button v-else type="primary" loading round disabled>生成中…</n-button>
                    </div>
                  </div>
                </div>
              </template>

              <template #2>
                <div class="right-panel">
                  <BiblePanel v-if="rightPanel === 'bible'" :key="biblePanelKey" :slug="slug" />
                  <KnowledgePanel v-else :slug="slug" />
                </div>
              </template>
            </n-split>
          </template>
        </n-split>
      </div>
    </n-spin>

    <n-modal
      v-model:show="showPlanModal"
      preset="card"
      style="width: min(460px, 94vw)"
      :mask-closable="false"
      title="结构规划"
    >
      <n-space vertical :size="16">
        <n-text depth="3">
          首次生成适用于尚无圣经与大纲；「再规划」会结合滚动摘要、编务远期摘要与已完成章节信息，修订 bible 与分章大纲。
        </n-text>
        <n-radio-group v-model:value="planMode">
          <n-space vertical :size="8">
            <n-radio value="initial">首次生成圣经与分章大纲</n-radio>
            <n-radio value="revise" :disabled="!hasStructure">基于进度再规划（需已有 bible / outline）</n-radio>
          </n-space>
        </n-radio-group>
        <n-checkbox v-model:checked="planDryRun">预演（dry-run，不调用模型）</n-checkbox>
        <n-space justify="end" :size="10">
          <n-button @click="showPlanModal = false">取消</n-button>
          <n-button type="primary" @click="confirmPlan">开始</n-button>
        </n-space>
      </n-space>
    </n-modal>

    <n-modal
      v-model:show="showTaskModal"
      preset="card"
      style="width: min(420px, 92vw)"
      :mask-closable="false"
      :segmented="{ content: true }"
      title="任务进行中"
    >
      <n-space vertical :size="16">
        <n-progress type="line" :percentage="taskProgress" :processing="taskProgress < 100" :height="10" />
        <n-text>{{ taskMessage }}</n-text>
        <n-button size="small" secondary @click="cancelRunningTask">终止任务</n-button>
      </n-space>
    </n-modal>

    <n-drawer
      v-model:show="streamDraftVisible"
      :height="420"
      placement="bottom"
      :trap-focus="false"
      :auto-focus="false"
    >
      <n-drawer-content title="流式撰稿区（正文同步，可编辑）" closable>
        <n-input
          v-model:value="streamText"
          type="textarea"
          placeholder="生成中正文会追加到此；可边生成边改。"
          :autosize="{ minRows: 14, maxRows: 28 }"
          class="stream-draft-input"
        />
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { bookApi, chatApi, jobApi } from '../api/book'
import { marked } from 'marked'
import KnowledgePanel from '../components/KnowledgePanel.vue'
import BiblePanel from '../components/BiblePanel.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const slug = route.params.slug as string
const bookTitle = ref('')
const chapters = ref<any[]>([])
const messages = ref<any[]>([])
const inputMessage = ref('')
const sending = ref(false)
/** 对话上下文：full 带多轮；fresh 仅本轮用户句 + 全书 system */
const historyMode = ref<'full' | 'fresh'>('full')
const historySegmentOptions = [
  { label: '带历史', value: 'full' },
  { label: '仅本轮', value: 'fresh' },
]
const chapterPick = ref<number | null>(null)
/** 与「清空上下文」下拉不同：仅本条 user 写入前清空 thread */
const clearBeforeSend = ref(false)
/** 开启时用 SSE：工具步骤实时展示 + 正文分块；关闭时用原有一轮非流式请求 */
const useStreamMode = ref(true)
/** 生成开始时若勾选则自动打开底部抽屉，与 streamText 双向同步便于边生成边改 */
const useStreamDraft = ref(false)
const streamDraftVisible = ref(false)
const streamActive = ref(false)
const streamText = ref('')
const streamTools = ref<Array<{ name: string; ok: boolean; detail: string }>>([])

const rightPanel = ref<'bible' | 'knowledge'>('knowledge')
const biblePanelKey = ref(0)
const pageLoading = ref(true)

const messageScrollRef = ref<{ scrollTo: (o: { top?: number; behavior?: ScrollBehavior }) => void } | null>(null)

const showPlanModal = ref(false)
const planMode = ref<'initial' | 'revise'>('initial')
const planDryRun = ref(false)
const bookMeta = ref<{ has_bible?: boolean; has_outline?: boolean }>({})
const hasStructure = computed<boolean>(
  () => !!(bookMeta.value.has_bible && bookMeta.value.has_outline)
)

const showTaskModal = ref(false)
const taskProgress = ref(0)
const taskMessage = ref('')
const currentJobId = ref<string | null>(null)
let taskTimer: number | null = null

const currentChapterId = computed(() => {
  if (route.name === 'Chapter') return Number(route.params.id)
  return null
})

const chapterSelectOptions = computed(() =>
  chapters.value.map(c => ({ label: `第${c.id}章 ${c.title ? c.title.slice(0, 8) : ''}`, value: c.id }))
)

const clearMenuOptions = [
  { label: '仅清空对话', key: 'thread' },
  { label: '对话 + 远期摘要', key: 'both' },
]

watch(
  chapters,
  ch => {
    if (!ch?.length) {
      chapterPick.value = null
      return
    }
    if (chapterPick.value == null || !ch.some((x: { id: number }) => x.id === chapterPick.value)) {
      chapterPick.value = ch[0].id
    }
  },
  { immediate: true }
)

watch(currentChapterId, id => {
  if (id != null && !Number.isNaN(id)) chapterPick.value = id
})

watch([streamText, streamTools], () => {
  if (streamActive.value) scrollToBottom()
})

const onClearMenu = async (key: string | number) => {
  const k = String(key)
  try {
    await chatApi.clearThread(slug, k === 'both')
    await fetchMessages()
    message.success(k === 'both' ? '已清空对话与远期摘要' : '已清空对话记录')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '清空失败')
  }
}

const fillQuick = (kind: 'chapter' | 'batch' | 'check') => {
  const n = chapterPick.value ?? chapters.value[0]?.id ?? 1
  if (kind === 'chapter') {
    inputMessage.value = `请结合分章大纲与侧栏叙事，协助撰写第 ${n} 章：先给出节拍/子段落，再说明将调用的工具（如 story_upsert_chapter_summary）及字段；人物关系以 cast_* 为准。`
  } else if (kind === 'batch') {
    inputMessage.value =
      '请规划并调用工具，批量更新第 __ 章至第 __ 章的章摘要（story_upsert_chapter_summary），保持梗概锁定与关系图一致；先列章号计划再逐步执行。'
  } else {
    inputMessage.value =
      '请对照 manifest 与侧栏「梗概锁定」，检查当前叙事风险；必要时先 story_get_snapshot 再给出修订建议。'
  }
}

const setRightPanel = (p: 'bible' | 'knowledge') => {
  rightPanel.value = p
}

const loadDesk = async () => {
  const res = await bookApi.getDesk(slug)
  bookTitle.value = res.book?.title || slug
  chapters.value = res.chapters || []
  bookMeta.value = {
    has_bible: res.book?.has_bible,
    has_outline: res.book?.has_outline,
  }
}

const fetchMessages = async () => {
  const res = await chatApi.getMessages(slug)
  messages.value = res.messages || []
  await nextTick()
  scrollToBottom()
}

const scrollToBottom = () => {
  nextTick(() => {
    messageScrollRef.value?.scrollTo({ top: 999999, behavior: 'smooth' })
  })
}

/** Enter 发送；Ctrl/Cmd+Enter 插入换行；Shift+Enter 保持默认换行 */
const onComposerKeydown = (e: KeyboardEvent) => {
  if (e.key !== 'Enter') return
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault()
    const el = e.target as HTMLTextAreaElement
    const start = el.selectionStart ?? 0
    const end = el.selectionEnd ?? 0
    const v = inputMessage.value
    inputMessage.value = v.slice(0, start) + '\n' + v.slice(end)
    nextTick(() => {
      el.selectionStart = el.selectionEnd = start + 1
    })
    return
  }
  if (e.shiftKey) return
  e.preventDefault()
  void sendMessage()
}

const parseSseLine = (line: string): Record<string, unknown> | null => {
  if (!line.startsWith('data: ')) return null
  try {
    return JSON.parse(line.slice(6)) as Record<string, unknown>
  } catch {
    return null
  }
}

const sendMessageStream = async (userMessage: string, clearFlag: boolean) => {
  streamTools.value = []
  streamText.value = ''
  streamActive.value = true
  if (useStreamDraft.value) streamDraftVisible.value = true
  scrollToBottom()

  let res: Response
  try {
    res = await chatApi.sendStream(slug, userMessage, {
      use_cast_tools: true,
      history_mode: historyMode.value,
      clear_thread: clearFlag,
    })
  } catch {
    streamActive.value = false
    message.error('网络错误')
    return
  }

  clearBeforeSend.value = false
  if (!res.ok || !res.body) {
    streamActive.value = false
    const text = await res.text().catch(() => '')
    message.error(text || `请求失败 ${res.status}`)
    return
  }

  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      let sep: number
      while ((sep = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, sep)
        buf = buf.slice(sep + 2)
        for (const line of block.split('\n')) {
          const json = parseSseLine(line)
          if (!json) continue
          const typ = json.type as string
          if (typ === 'tool') {
            streamTools.value = [
              ...streamTools.value,
              {
                name: String(json.name ?? ''),
                ok: !!json.ok,
                detail: String(json.detail ?? ''),
              },
            ]
          } else if (typ === 'chunk') {
            streamText.value += String(json.text ?? '')
          } else if (typ === 'done') {
            await fetchMessages()
            scrollToBottom()
          } else if (typ === 'error') {
            message.error(String(json.message ?? '生成失败'))
            await fetchMessages()
          }
        }
      }
    }
  } finally {
    streamActive.value = false
    streamText.value = ''
    streamTools.value = []
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || sending.value) return

  const userMessage = inputMessage.value
  inputMessage.value = ''
  sending.value = true
  const clearFlag = clearBeforeSend.value
  try {
    if (useStreamMode.value) {
      await sendMessageStream(userMessage, clearFlag)
    } else {
      const res = await chatApi.send(slug, userMessage, {
        use_cast_tools: true,
        history_mode: historyMode.value,
        clear_thread: clearFlag,
      })
      clearBeforeSend.value = false
      if (res.ok) {
        await fetchMessages()
      } else {
        message.warning(res.reply || '未生成回复')
      }
    }
  } catch (error: any) {
    message.error(error?.response?.data?.detail || '发送失败')
  } finally {
    sending.value = false
  }
}

// 侧栏知识检索「引用到输入框」
const onComposerInsert = (ev: any) => {
  const text = (ev?.detail?.text || '').toString()
  if (!text.trim()) return
  if (!inputMessage.value.trim()) inputMessage.value = text
  else inputMessage.value = inputMessage.value.trimEnd() + '\n\n' + text
}

onMounted(() => {
  window.addEventListener('aitext:composer:insert', onComposerInsert as any)
})

onUnmounted(() => {
  window.removeEventListener('aitext:composer:insert', onComposerInsert as any)
})

const openPlanModal = () => {
  planMode.value = hasStructure.value ? 'revise' : 'initial'
  planDryRun.value = false
  showPlanModal.value = true
}

const confirmPlan = async () => {
  showPlanModal.value = false
  try {
    const res = await jobApi.startPlan(slug, planDryRun.value, planMode.value)
    startPolling(res.job_id)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '启动失败')
  }
}

const startWrite = async () => {
  try {
    const res = await jobApi.startWrite(slug, 1)
    startPolling(res.job_id)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '启动失败')
  }
}

const startPolling = (jobId: string) => {
  currentJobId.value = jobId
  showTaskModal.value = true
  taskProgress.value = 6
  taskMessage.value = '任务启动中…'
  let bump = 6

  taskTimer = window.setInterval(async () => {
    bump = Math.min(93, bump + 2 + Math.random() * 6)
    taskProgress.value = Math.floor(bump)
    try {
      const status = await jobApi.getStatus(jobId)
      taskMessage.value = status.message || status.phase || '执行中…'

      if (status.status === 'done') {
        taskProgress.value = 100
        stopPolling()
        message.success('任务完成')
        await loadDesk()
        await fetchMessages()
        biblePanelKey.value += 1
      } else if (status.status === 'cancelled') {
        taskProgress.value = 100
        stopPolling()
        message.info('任务已终止')
        await loadDesk()
      } else if (status.status === 'error') {
        stopPolling()
        message.error(status.error || '任务失败')
      }
    } catch {
      stopPolling()
    }
  }, 1000)
}

const cancelRunningTask = async () => {
  const jid = currentJobId.value
  if (!jid) return
  try {
    await jobApi.cancelJob(jid)
    taskMessage.value = '正在终止…'
  } catch (error: any) {
    message.error(error?.response?.data?.detail || '终止失败')
  }
}

const stopPolling = () => {
  if (taskTimer) {
    clearInterval(taskTimer)
    taskTimer = null
  }
  currentJobId.value = null
  showTaskModal.value = false
}

const goHome = () => {
  router.push('/')
}

const goToChapter = (id: number) => {
  router.push(`/book/${slug}/chapter/${id}`)
}

const getRoleLabel = (role: string, meta?: { tools?: unknown[] }) => {
  if (role === 'assistant' && meta?.tools?.length) return '助手 · 工具'
  const map: Record<string, string> = { user: '我', assistant: '助手', system: '系统' }
  return map[role] || role
}

const getRoleType = (role: string) => {
  const map: Record<string, any> = { user: 'info', assistant: 'default', system: 'warning' }
  return map[role] || 'default'
}

const renderMarkdown = (content: string) => {
  return marked.parse(content || '', { breaks: true, async: false }) as string
}

const formatTime = (ts: string) => {
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

onMounted(async () => {
  try {
    await loadDesk()
    await fetchMessages()
  } catch {
    message.error('加载失败，请检查网络与后端是否已启动')
    bookTitle.value = slug
  } finally {
    pageLoading.value = false
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.workbench {
  height: 100vh;
  min-height: 0;
  background: var(--app-page-bg, #f0f2f8);
}

.workbench-spin {
  height: 100%;
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

.chat-area {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--app-surface, #fff);
}

.chat-header {
  flex-shrink: 0;
  padding: 12px 16px;
  border-bottom: 1px solid var(--aitext-split-border);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
}

.chat-header-actions {
  max-width: 100%;
}

.chat-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.chat-sub {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  font-family: ui-monospace, monospace;
}

.chat-messages {
  flex: 1;
  min-height: 0;
}

.chat-messages-pad {
  padding: 16px 18px 24px;
  max-width: 900px;
  margin: 0 auto;
}

.msg-row {
  display: flex;
  margin-bottom: 14px;
  animation: msg-in 0.28s ease both;
}

@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant,
.msg-row.system {
  justify-content: flex-start;
}

.msg-bubble {
  max-width: min(92%, 720px);
  padding: 12px 14px;
  border-radius: 14px;
  box-shadow: var(--app-shadow);
}

.msg-row.user .msg-bubble {
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff;
}

.msg-row.user .msg-bubble .msg-time {
  color: rgba(255, 255, 255, 0.85);
}

.msg-row.assistant .msg-bubble,
.msg-row.system .msg-bubble {
  background: #f1f5f9;
  border: 1px solid var(--app-border);
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.msg-time {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.msg-row.user :deep(.n-tag) {
  --n-color: rgba(255, 255, 255, 0.85);
  --n-text-color: #1e1b4b;
}

.msg-md {
  color: inherit;
}

.msg-row.user .msg-md :deep(a) {
  color: #e0e7ff;
}

.composer {
  flex-shrink: 0;
  padding: 12px 16px 16px;
  border-top: 1px solid var(--aitext-split-border);
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--app-surface);
}

.composer-input :deep(textarea) {
  font-size: 14px;
  line-height: 1.5;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
}

.right-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--aitext-panel-muted);
  border-left: 1px solid var(--aitext-split-border);
}

.composer-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.ch-pick-select {
  min-width: 140px;
  max-width: 200px;
}

.clear-before-check {
  font-size: 12px;
}

.quick-prompts {
  margin-bottom: 6px;
}

.msg-tools {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(79, 70, 229, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.18);
}

.msg-tools-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #6366f1;
  margin-bottom: 6px;
  letter-spacing: 0.04em;
}

.msg-tool-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}

.msg-tool-line:last-child {
  margin-bottom: 0;
}

.msg-tool-detail {
  color: #475569;
  line-height: 1.45;
  flex: 1;
  min-width: 0;
}

.stream-live .stream-live-bubble {
  border: 1px dashed rgba(99, 102, 241, 0.45);
  background: linear-gradient(180deg, #fafbff 0%, #f1f5f9 100%);
}

.stream-thinking {
  background: rgba(79, 70, 229, 0.07);
}

.stream-md {
  min-height: 1.25em;
}

.stream-draft-input :deep(textarea) {
  font-size: 14px;
  line-height: 1.55;
  font-family: ui-monospace, 'Cascadia Code', 'Segoe UI Mono', monospace;
}
</style>
