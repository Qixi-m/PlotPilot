<template>
  <div class="kp-root">
    <header class="kp-hero">
      <div class="kp-hero-copy">
        <h3 class="kp-title">侧栏资料</h3>
        <p class="kp-lead">
          可在「叙事与知识」「关系图」「三元组图谱」间切换：叙事含梗概锁定、章摘要与三元组编辑；关系图为
          <code>cast</code> 人物网（与独立页同源）；三元组图谱由事实表生成力导向图，便于查看「主—谓—宾」网络。书目级梗概以
          <strong>manifest</strong> 为准。
        </p>
      </div>
      <n-button
        v-show="sideTab === 'narrative'"
        type="primary"
        size="small"
        :loading="saving"
        round
        @click="save"
      >
        保存到全书上下文
      </n-button>
    </header>

    <n-segmented
      v-model:value="sideTab"
      class="kp-seg"
      size="small"
      block
      :options="[
        { label: '叙事与知识', value: 'narrative' },
        { label: '关系图', value: 'graph' },
        { label: '三元组图谱', value: 'triple' },
      ]"
    />

    <div v-show="sideTab === 'narrative'" class="kp-banner">
      <span class="kp-banner-dot" aria-hidden="true" />
      <span class="kp-banner-text">
        梗概锁定、分章叙事与三元组可由工具（<code>story_*</code> / <code>kg_*</code>）写入，也可在此手改后保存。每章「节拍」对应大纲子段落；人物名请与关系图一致。
      </span>
    </div>

    <n-tabs
      v-show="sideTab === 'narrative'"
      v-model:value="subTab"
      type="line"
      size="small"
      animated
      class="kp-subtabs"
    >
      <n-tab-pane name="search" tab="检索">
        <n-card class="kp-search" size="small" :bordered="false">
          <n-space align="center" :size="10" wrap>
            <n-input
              v-model:value="searchQ"
              size="small"
              placeholder="全书知识检索：人物、关系、章摘要、事实…"
              class="kp-search-input"
              @keydown.enter.prevent="doSearch"
            />
            <n-button size="small" secondary :loading="searching" @click="doSearch">检索</n-button>
            <n-button size="small" quaternary @click="useHitToComposer" :disabled="!selectedHit">
              引用到输入框
            </n-button>
          </n-space>
          <div v-if="searchHits.length" class="kp-search-list">
            <div
              v-for="(h, i) in searchHits"
              :key="h.id || i"
              class="kp-hit"
              :class="{ active: selectedHit === h }"
              @click="selectedHit = h"
            >
              <div class="kp-hit-meta">
                <n-tag size="tiny" round :bordered="false">{{ h.meta?.type || '资料' }}</n-tag>
                <span class="kp-hit-id">{{ h.meta?.id || h.id || '' }}</span>
              </div>
              <div class="kp-hit-text">{{ h.text }}</div>
            </div>
          </div>
          <div v-else class="kp-search-empty">
            <n-text depth="3" style="font-size: 12px">提示：先用工具把资料写入侧栏，检索命中会更稳定。</n-text>
          </div>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="premise" tab="梗概锁定">
        <section class="kp-section">
        <div class="kp-section-head">
          <span class="kp-section-icon">◆</span>
          <span class="kp-section-title">梗概锁定</span>
          <n-tag size="tiny" round :bordered="false" class="kp-tag-tool">story_set_premise_lock</n-tag>
        </div>
        <n-card size="small" class="kp-card kp-card-premise" :bordered="false">
          <n-input
            v-model:value="data.premise_lock"
            type="textarea"
            :autosize="{ minRows: 5, maxRows: 18 }"
            placeholder="主线、不可违背设定、结局走向（与 manifest 互补，防百万字跑篇）…"
            class="kp-textarea"
          />
        </n-card>
        </section>
      </n-tab-pane>

      <n-tab-pane name="chapters" tab="分章叙事">
        <section class="kp-section">
        <div class="kp-section-head">
          <span class="kp-section-icon">◇</span>
          <span class="kp-section-title">分章叙事</span>
          <n-tag size="tiny" round :bordered="false" class="kp-tag-tool">story_upsert_chapter_summary</n-tag>
        </div>
        <p class="kp-section-hint">章标题来自书目大纲；每章含节拍子段、章末总结与同步状态。</p>

        <div class="kp-chapters">
          <n-card
            v-for="ch in sortedChapters"
            :key="ch.chapter_id"
            size="small"
            class="kp-card kp-ch-card"
            :bordered="false"
          >
            <template #header>
              <div class="kp-ch-head">
                <div class="kp-ch-title">
                  <span class="kp-ch-num">第 {{ ch.chapter_id }} 章</span>
                  <span v-if="chapterTitle(ch.chapter_id)" class="kp-ch-outline">{{ chapterTitle(ch.chapter_id) }}</span>
                </div>
                <n-select
                  v-model:value="ch.sync_status"
                  size="tiny"
                  class="kp-sync-select"
                  :options="syncOptions"
                />
              </div>
            </template>

            <div class="kp-ch-body">
              <div class="kp-field">
                <label class="kp-label">大纲下子段落 · 节拍</label>
                <n-dynamic-input
                  v-model:value="ch.beat_sections"
                  :min="0"
                  :on-create="() => ''"
                  placeholder="每行一条：如「夜袭前奏 · 主角与 X 对峙」"
                  class="kp-dynamic"
                />
              </div>

              <div class="kp-field">
                <label class="kp-label">章末总结</label>
                <n-input
                  v-model:value="ch.summary"
                  type="textarea"
                  :autosize="{ minRows: 3, maxRows: 12 }"
                  placeholder="本章收束叙述，供上下文与工具对齐…"
                  class="kp-textarea"
                />
              </div>

              <div class="kp-grid-2">
                <div class="kp-field">
                  <label class="kp-label">人物与关键事件</label>
                  <n-input
                    v-model:value="ch.key_events"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 8 }"
                    placeholder="与关系图人物名一致，便于图谱与叙事对齐…"
                    class="kp-textarea"
                  />
                </div>
                <div class="kp-field">
                  <label class="kp-label">埋线 / 未解</label>
                  <n-input
                    v-model:value="ch.open_threads"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 8 }"
                    placeholder="伏笔、未解问题…"
                    class="kp-textarea"
                  />
                </div>
              </div>

              <div class="kp-field">
                <label class="kp-label">一致性说明</label>
                <n-input
                  v-model:value="ch.consistency_note"
                  type="textarea"
                  :autosize="{ minRows: 2, maxRows: 6 }"
                  placeholder="与前章 / 大纲 / 梗概锁定的对齐说明…"
                  class="kp-textarea"
                />
              </div>

              <div class="kp-ch-foot">
                <n-button size="tiny" quaternary type="error" @click="removeChapterById(ch.chapter_id)">
                  移除此章条目
                </n-button>
                <n-button size="tiny" quaternary @click="goCastChapter(ch.chapter_id)">全页关系网 · 本章</n-button>
              </div>
            </div>
          </n-card>
        </div>

        <n-button dashed block class="kp-add-ch" @click="addChapter">+ 添加一章叙事块</n-button>
        </section>
      </n-tab-pane>

      <n-tab-pane name="facts" tab="三元组">
        <section class="kp-section">
        <div class="kp-section-head">
          <span class="kp-section-icon">◎</span>
          <span class="kp-section-title">知识三元组</span>
          <n-tag size="tiny" round :bordered="false" class="kp-tag-tool">kg_upsert_fact</n-tag>
        </div>
        <p class="kp-section-hint">事实型约束；主语/宾语可与人物图谱姓名对应，并标注出处章号。</p>

        <div class="kp-facts">
          <div v-for="(f, fi) in data.facts" :key="f.id" class="kp-fact">
            <div class="kp-fact-id">{{ f.id }}</div>
            <div class="kp-fact-grid">
              <n-input v-model:value="f.subject" placeholder="主语" size="small" />
              <n-input v-model:value="f.predicate" placeholder="关系" size="small" />
              <n-input v-model:value="f.object" placeholder="宾语" size="small" />
              <n-input
                :value="factChapterText(f)"
                placeholder="章号"
                size="small"
                class="kp-fact-ch"
                @update:value="wrapSetFactChapter(f)($event)"
              />
              <n-input v-model:value="f.note" placeholder="备注" size="small" class="kp-fact-note" />
            </div>
            <n-button size="tiny" quaternary type="error" @click="removeFact(fi)">删除</n-button>
          </div>
        </div>
        <n-button dashed block class="kp-add-ch" @click="addFact">+ 添加三元组</n-button>
        </section>
      </n-tab-pane>
    </n-tabs>

    <CastGraphCompact v-if="sideTab === 'graph'" :slug="slug" class="kp-graph-embed" />
    <KnowledgeTripleGraph v-if="sideTab === 'triple'" :slug="slug" class="kp-graph-embed" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { bookApi } from '../api/book'
import CastGraphCompact from './CastGraphCompact.vue'
import KnowledgeTripleGraph from './KnowledgeTripleGraph.vue'

const props = defineProps<{ slug: string }>()
const router = useRouter()
const message = useMessage()

interface Ch {
  chapter_id: number
  summary: string
  key_events: string
  open_threads: string
  consistency_note: string
  beat_sections: string[]
  sync_status: string
}

interface Fact {
  id: string
  subject: string
  predicate: string
  object: string
  chapter_id: number | null
  note: string
}

const data = ref({
  version: 1,
  premise_lock: '',
  chapters: [] as Ch[],
  facts: [] as Fact[],
})

const saving = ref(false)
const sideTab = ref<'narrative' | 'graph' | 'triple'>('narrative')
const subTab = ref<'search' | 'premise' | 'chapters' | 'facts'>('search')
const outlineTitles = ref<Record<number, string>>({})
const searchQ = ref('')
const searching = ref(false)
const searchHits = ref<any[]>([])
const selectedHit = ref<any | null>(null)

const doSearch = async () => {
  const q = searchQ.value.trim()
  if (!q) return
  searching.value = true
  try {
    const r = await bookApi.knowledgeSearch(props.slug, q, 8)
    searchHits.value = r.hits || []
    selectedHit.value = searchHits.value[0] || null
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '检索失败')
  } finally {
    searching.value = false
  }
}

const useHitToComposer = () => {
  if (!selectedHit.value) return
  const t = String(selectedHit.value.text || '').trim()
  if (!t) return
  // Workbench.vue 监听该事件，将文本插入输入框
  window.dispatchEvent(new CustomEvent('aitext:composer:insert', { detail: { text: t } }))
  message.success('已引用到输入框')
}

const syncOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已对齐', value: 'synced' },
  { label: '待更新', value: 'stale' },
]

const sortedChapters = computed(() =>
  [...data.value.chapters].sort((a, b) => a.chapter_id - b.chapter_id)
)

const chapterTitle = (cid: number) => outlineTitles.value[cid] || ''

const loadOutlineTitles = async () => {
  try {
    const d = await bookApi.getDesk(props.slug)
    const m: Record<number, string> = {}
    for (const ch of d.chapters || []) {
      if (ch.id != null) m[Number(ch.id)] = (ch.title || '').trim()
    }
    outlineTitles.value = m
  } catch {
    outlineTitles.value = {}
  }
}

const load = async () => {
  try {
    const k = await bookApi.getKnowledge(props.slug)
    data.value = {
      version: k.version ?? 1,
      premise_lock: k.premise_lock || '',
      chapters: (k.chapters || []).map((c: any) => ({
        chapter_id: c.chapter_id,
        summary: c.summary || '',
        key_events: c.key_events || '',
        open_threads: c.open_threads || '',
        consistency_note: c.consistency_note || '',
        beat_sections: Array.isArray(c.beat_sections) ? [...c.beat_sections] : [],
        sync_status: (() => {
          const s = String(c.sync_status || 'draft').toLowerCase()
          return ['draft', 'synced', 'stale'].includes(s) ? s : 'draft'
        })(),
      })),
      facts: (k.facts || []).map((f: any) => ({
        id: f.id,
        subject: f.subject || '',
        predicate: f.predicate || '',
        object: f.object || '',
        chapter_id: f.chapter_id ?? null,
        note: f.note || '',
      })),
    }
    await loadOutlineTitles()
  } catch {
    message.error('加载叙事知识失败')
  }
}

const save = async () => {
  saving.value = true
  try {
    await bookApi.putKnowledge(props.slug, {
      ...data.value,
      chapters: sortedChapters.value.map(c => ({
        ...c,
        chapter_id: Number(c.chapter_id),
        beat_sections: (c.beat_sections || []).map(s => String(s || '').trim()).filter(Boolean),
        sync_status: (c.sync_status || 'draft').toLowerCase(),
      })),
      facts: data.value.facts.map(f => ({
        ...f,
        id: f.id || `f_${Math.random().toString(36).slice(2, 10)}`,
        chapter_id: f.chapter_id == null ? null : Number(f.chapter_id),
      })),
    })
    message.success('已保存并进入全书上下文')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const addChapter = () => {
  const ids = data.value.chapters.map(c => c.chapter_id)
  const next = ids.length ? Math.max(...ids) + 1 : 1
  data.value.chapters.push({
    chapter_id: next,
    summary: '',
    key_events: '',
    open_threads: '',
    consistency_note: '',
    beat_sections: [],
    sync_status: 'draft',
  })
}

const removeChapterById = (cid: number) => {
  data.value.chapters = data.value.chapters.filter(c => c.chapter_id !== cid)
}

const addFact = () => {
  data.value.facts.push({
    id: `f_${Math.random().toString(36).slice(2, 12)}`,
    subject: '',
    predicate: '',
    object: '',
    chapter_id: null,
    note: '',
  })
}

const removeFact = (fi: number) => {
  data.value.facts.splice(fi, 1)
}

const goCastChapter = (cid: number) => {
  router.push({ path: `/book/${props.slug}/cast`, query: { chapter: String(cid) } })
}

const factChapterText = (f: Fact) =>
  f.chapter_id != null && f.chapter_id >= 1 ? String(f.chapter_id) : ''

const setFactChapter = (f: Fact, v: string) => {
  const n = parseInt(String(v ?? '').trim(), 10)
  f.chapter_id = Number.isFinite(n) && n >= 1 ? n : null
}

const wrapSetFactChapter = (f: Fact) => (v: string) => setFactChapter(f, v)

watch(
  () => props.slug,
  () => {
    void load()
  }
)

onMounted(() => {
  void load()
})
</script>

<style scoped>
.kp-root {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 12px 8px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
}

.kp-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.kp-title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: #0f172a;
}

.kp-lead {
  margin: 0;
  font-size: 12px;
  line-height: 1.65;
  color: #475569;
  max-width: 520px;
}

.kp-lead strong {
  color: #334155;
}

.kp-lead code {
  font-size: 11px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(79, 70, 229, 0.08);
  color: #4338ca;
}

.kp-banner {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  margin-bottom: 12px;
  border-radius: 10px;
  background: rgba(79, 70, 229, 0.06);
  border: 1px solid rgba(79, 70, 229, 0.12);
  flex-shrink: 0;
}

.kp-banner-dot {
  width: 6px;
  height: 6px;
  margin-top: 6px;
  border-radius: 50%;
  background: #6366f1;
  flex-shrink: 0;
}

.kp-banner-text {
  font-size: 11px;
  line-height: 1.55;
  color: #475569;
}

.kp-scroll {
  flex: 1;
  min-height: 0;
}

.kp-subtabs {
  flex: 1;
  min-height: 0;
  margin-top: 10px;
}

.kp-subtabs :deep(.n-tabs-nav) {
  padding: 0 2px 6px;
}

.kp-subtabs :deep(.n-tab-pane) {
  padding-top: 6px;
}

.kp-section {
  margin-bottom: 18px;
}

.kp-section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.kp-section-icon {
  color: #94a3b8;
  font-size: 12px;
}

.kp-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.kp-tag-tool {
  font-size: 10px !important;
  font-family: ui-monospace, monospace;
  color: #6366f1 !important;
  background: rgba(99, 102, 241, 0.12) !important;
}

.kp-section-hint {
  margin: 0 0 10px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.5;
}

.kp-card {
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.kp-card-premise {
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.06) !important;
}

.kp-textarea :deep(textarea) {
  font-size: 13px;
  line-height: 1.6;
}

.kp-chapters {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kp-ch-card {
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.07) !important;
  overflow: hidden;
}

.kp-ch-card :deep(.n-card-header) {
  padding: 10px 14px;
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.06), transparent);
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.kp-ch-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.kp-ch-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.kp-ch-num {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.kp-ch-outline {
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kp-sync-select {
  width: 108px;
  flex-shrink: 0;
}

.kp-ch-body {
  padding-top: 4px;
}

.kp-field {
  margin-bottom: 12px;
}

.kp-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}

.kp-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

@media (max-width: 520px) {
  .kp-grid-2 {
    grid-template-columns: 1fr;
  }
}

.kp-dynamic :deep(.n-dynamic-input-item) {
  margin-bottom: 6px;
}

.kp-ch-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px dashed rgba(15, 23, 42, 0.08);
}

.kp-add-ch {
  margin-top: 4px;
}

.kp-facts {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kp-fact {
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.07);
}

.kp-fact-id {
  font-size: 10px;
  font-family: ui-monospace, monospace;
  color: #94a3b8;
  margin-bottom: 8px;
}

.kp-fact-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}

.kp-fact-note {
  grid-column: 1 / -1;
}

.kp-fact-ch {
  max-width: 88px;
}

.kp-seg {
  flex-shrink: 0;
  margin-bottom: 10px;
}

.kp-graph-embed {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
