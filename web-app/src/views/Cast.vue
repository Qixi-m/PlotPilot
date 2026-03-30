<template>
  <div class="cast-page">
    <header class="cast-header">
      <n-space align="center">
        <n-button quaternary round @click="goWorkbench">
          <template #icon><span class="ico">←</span></template>
          工作台
        </n-button>
        <n-divider vertical />
        <h1 class="cast-title">人物关系网</h1>
        <n-text depth="3">{{ slug }}</n-text>
      </n-space>
      <n-space>
        <n-input
          v-model:value="searchQ"
          placeholder="检索姓名、角色、关系…"
          clearable
          round
          style="width: 260px"
          @update:value="onSearch"
        />
        <n-button secondary @click="reload">刷新</n-button>
        <n-button type="primary" :loading="saving" @click="saveAll">保存</n-button>
      </n-space>
    </header>

    <div class="cast-body">
      <div ref="netContainer" class="net-wrap" />
      <aside class="cast-side">
        <n-collapse :default-expanded-names="['cov']" class="cov-collapse">
          <n-collapse-item title="正文与关系图" name="cov">
            <n-spin :show="covLoading" size="small">
              <template v-if="coverage">
                <n-text depth="3" class="cov-meta">
                  已扫描 {{ coverage.chapter_files_scanned }} 个章节文件
                  <template v-if="chapterFilter != null"> · 当前筛选第 {{ chapterFilter }} 章</template>
                </n-text>

                <div class="cov-block">
                  <div class="cov-block-title">关系图内角色</div>
                  <div v-for="row in visibleCastRows" :key="row.id" class="cov-row">
                    <div class="cov-row-main">
                      <n-button text type="primary" size="small" @click="focusCastNode(row.id)">
                        {{ row.name }}
                      </n-button>
                      <n-tag v-if="row.mentioned" size="small" type="success" round>正文已出现</n-tag>
                      <n-tag v-else size="small" type="warning" round>正文未见</n-tag>
                    </div>
                    <n-space v-if="row.chapter_ids.length" size="small" class="cov-chapters">
                      <n-button
                        v-for="cid in row.chapter_ids"
                        :key="cid"
                        size="tiny"
                        quaternary
                        :disabled="cid === 0"
                        @click="goChapter(cid)"
                      >
                        {{ cid === 0 ? '合并稿' : `第${cid}章` }}
                      </n-button>
                    </n-space>
                  </div>
                </div>

                <div v-if="coverage.bible_not_in_cast.length" class="cov-block">
                  <div class="cov-block-title">设定中有、关系图中尚无</div>
                  <div v-for="(b, i) in coverage.bible_not_in_cast" :key="'b' + i" class="cov-row">
                    <span class="cov-name">{{ b.name }}</span>
                    <n-tag v-if="b.in_novel_text" size="small" type="warning" round>正文已出现</n-tag>
                    <n-tag v-else size="small" round>未见正文</n-tag>
                    <n-space v-if="b.chapter_ids.length" size="small" class="cov-chapters">
                      <n-button
                        v-for="cid in b.chapter_ids"
                        :key="cid"
                        size="tiny"
                        quaternary
                        :disabled="cid === 0"
                        @click="goChapter(cid)"
                      >
                        {{ cid === 0 ? '合并稿' : `第${cid}章` }}
                      </n-button>
                    </n-space>
                  </div>
                </div>

                <div v-if="coverage.quoted_not_in_cast.length" class="cov-block">
                  <div class="cov-block-title">书名号「」未匹配关系图（需核对是否为人名）</div>
                  <div v-for="(q, i) in coverage.quoted_not_in_cast" :key="'q' + i" class="cov-row cov-row-quote">
                    <span>「{{ q.text }}」</span>
                    <n-text depth="3" class="cov-count">×{{ q.count }}</n-text>
                    <n-space v-if="q.chapter_ids.length" size="small" class="cov-chapters">
                      <n-button
                        v-for="cid in q.chapter_ids"
                        :key="cid"
                        size="tiny"
                        quaternary
                        @click="goChapter(cid)"
                      >
                        第{{ cid }}章
                      </n-button>
                    </n-space>
                  </div>
                </div>
              </template>
              <n-text v-else-if="!covLoading" depth="3">未能加载对照数据</n-text>
            </n-spin>
          </n-collapse-item>
        </n-collapse>

        <n-tabs v-model:value="castPane" type="segment" animated>
          <n-tab-pane name="node" tab="人物">
            <n-form label-placement="top" class="side-form">
              <n-form-item label="ID（唯一）">
                <n-input v-model:value="formChar.id" placeholder="如 zhang_san" />
              </n-form-item>
              <n-form-item label="姓名">
                <n-input v-model:value="formChar.name" />
              </n-form-item>
              <n-form-item label="别名（逗号分隔）">
                <n-input v-model:value="formChar.aliasesStr" placeholder="张三, 小张" />
              </n-form-item>
              <n-form-item label="角色定位">
                <n-input v-model:value="formChar.role" />
              </n-form-item>
              <n-form-item label="特点">
                <n-input v-model:value="formChar.traits" type="textarea" :rows="2" />
              </n-form-item>
              <n-form-item label="备注">
                <n-input v-model:value="formChar.note" type="textarea" :rows="2" />
              </n-form-item>
              <n-form-item label="人物线事件（里程碑，可与章号对齐）">
                <div v-for="(ev, ei) in formChar.events" :key="ei" class="ev-row">
                  <n-input v-model:value="ev.id" size="small" placeholder="事件 id" class="ev-id" />
                  <n-input-number v-model:value="ev.chapter_id" :min="1" clearable size="small" placeholder="章" class="ev-ch" />
                  <n-select v-model:value="ev.importance" size="small" class="ev-imp" :options="impOptions" />
                  <n-input v-model:value="ev.summary" type="textarea" :rows="2" placeholder="事件描述" class="ev-sum" />
                  <n-button size="tiny" quaternary type="error" @click="removeCharEvent(ei)">删</n-button>
                </div>
                <n-button dashed size="tiny" block @click="addCharEvent">+ 添加事件</n-button>
              </n-form-item>
              <n-space>
                <n-button type="primary" @click="applyCharacter">写入图中</n-button>
                <n-button secondary @click="newCharacter">新建空节点</n-button>
                <n-button v-if="formChar.id" type="error" quaternary @click="removeCharacter">删除此人</n-button>
              </n-space>
            </n-form>
          </n-tab-pane>
          <n-tab-pane name="edge" tab="关系">
            <n-form label-placement="top" class="side-form">
              <n-form-item label="关系 ID">
                <n-input v-model:value="formRel.id" placeholder="可空自动生成" />
              </n-form-item>
              <n-form-item label="起点人物 ID">
                <n-input v-model:value="formRel.source_id" />
              </n-form-item>
              <n-form-item label="终点人物 ID">
                <n-input v-model:value="formRel.target_id" />
              </n-form-item>
              <n-form-item label="关系类型">
                <n-input v-model:value="formRel.label" placeholder="如 师徒、夫妻、敌对" />
              </n-form-item>
              <n-form-item label="备注">
                <n-input v-model:value="formRel.note" type="textarea" :rows="2" />
              </n-form-item>
              <n-form-item label="有向边">
                <n-switch v-model:value="formRel.directed" />
              </n-form-item>
              <n-form-item label="两人间共同经历 / 关键事件">
                <div v-for="(ev, ei) in formRel.events" :key="ei" class="ev-row">
                  <n-input v-model:value="ev.id" size="small" placeholder="事件 id" class="ev-id" />
                  <n-input-number v-model:value="ev.chapter_id" :min="1" clearable size="small" placeholder="章" class="ev-ch" />
                  <n-select v-model:value="ev.importance" size="small" class="ev-imp" :options="impOptions" />
                  <n-input v-model:value="ev.summary" type="textarea" :rows="2" placeholder="事件描述" class="ev-sum" />
                  <n-button size="tiny" quaternary type="error" @click="removeRelEvent(ei)">删</n-button>
                </div>
                <n-button dashed size="tiny" block @click="addRelEvent">+ 添加事件</n-button>
              </n-form-item>
              <n-space>
                <n-button type="primary" @click="applyRelationship">写入图中</n-button>
                <n-button v-if="formRel.id" type="error" quaternary @click="removeRelationship">删除此关系</n-button>
              </n-space>
            </n-form>
          </n-tab-pane>
        </n-tabs>
        <n-alert type="info" class="cast-hint" title="提示">
          点击节点编辑人物、点击边编辑关系；事件可手填或由对话里 cast_upsert_story_event 写入。开启流式输出时工具步骤会实时展示摘要（ReAct 感）。
        </n-alert>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import 'vis-network/styles/vis-network.css'
import { bookApi } from '../api/book'

interface StoryEventRow {
  id: string
  summary: string
  chapter_id: number | null
  importance: string
}

interface CastCharacter {
  id: string
  name: string
  aliases: string[]
  role: string
  traits: string
  note: string
  story_events?: Array<{ id: string; summary: string; chapter_id?: number | null; importance?: string }>
}

interface CastRelationship {
  id: string
  source_id: string
  target_id: string
  label: string
  note: string
  directed: boolean
  story_events?: Array<{ id: string; summary: string; chapter_id?: number | null; importance?: string }>
}

const route = useRoute()
const router = useRouter()
const message = useMessage()
const slug = route.params.slug as string

const netContainer = ref<HTMLElement | null>(null)
let network: Network | null = null

const graph = ref<{ characters: CastCharacter[]; relationships: CastRelationship[] }>({
  characters: [],
  relationships: [],
})

const searchQ = ref('')
const highlightIds = ref<Set<string>>(new Set())
const saving = ref(false)

interface CastCoveragePayload {
  chapter_files_scanned: number
  characters: Array<{ id: string; name: string; mentioned: boolean; chapter_ids: number[] }>
  bible_not_in_cast: Array<{
    name: string
    role: string
    in_novel_text: boolean
    chapter_ids: number[]
  }>
  quoted_not_in_cast: Array<{ text: string; count: number; chapter_ids: number[] }>
}

const coverage = ref<CastCoveragePayload | null>(null)
const covLoading = ref(false)

const chapterFilter = computed(() => {
  const c = route.query.chapter
  if (c == null || c === '') return null
  const n = parseInt(String(c), 10)
  return Number.isFinite(n) && n >= 0 ? n : null
})

const visibleCastRows = computed(() => {
  if (!coverage.value) return []
  const rows = coverage.value.characters
  const cf = chapterFilter.value
  if (cf == null) return rows
  return rows.filter(r => r.chapter_ids.includes(cf))
})

const castPane = ref<'node' | 'edge'>('node')
const impOptions = [
  { label: '通常', value: 'normal' },
  { label: '关键', value: 'key' },
]

const formChar = ref({
  id: '',
  name: '',
  aliasesStr: '',
  role: '',
  traits: '',
  note: '',
  events: [] as StoryEventRow[],
})

const formRel = ref({
  id: '',
  source_id: '',
  target_id: '',
  label: '',
  note: '',
  directed: true,
  events: [] as StoryEventRow[],
})

const mapEventsFromApi = (
  raw: CastCharacter['story_events'] | CastRelationship['story_events']
): StoryEventRow[] =>
  (raw || []).map(e => ({
    id: e.id || '',
    summary: e.summary || '',
    chapter_id: e.chapter_id != null && e.chapter_id >= 1 ? e.chapter_id : null,
    importance: e.importance || 'normal',
  }))

const normalizeStoryEvents = (rows: StoryEventRow[]) => {
  const out: Array<{ id: string; summary: string; chapter_id?: number; importance: string }> = []
  for (const e of rows) {
    const sum = (e.summary || '').trim()
    if (!sum) continue
    let id = (e.id || '').trim()
    if (!id) id = `ev_${Math.random().toString(36).slice(2, 11)}`
    const ch = e.chapter_id != null && e.chapter_id >= 1 ? e.chapter_id : undefined
    out.push({
      id,
      summary: sum,
      ...(ch != null ? { chapter_id: ch } : {}),
      importance: e.importance || 'normal',
    })
  }
  return out
}

const addCharEvent = () => {
  formChar.value.events.push({
    id: '',
    summary: '',
    chapter_id: null,
    importance: 'normal',
  })
}
const removeCharEvent = (ei: number) => {
  formChar.value.events.splice(ei, 1)
}
const addRelEvent = () => {
  formRel.value.events.push({
    id: '',
    summary: '',
    chapter_id: null,
    importance: 'normal',
  })
}
const removeRelEvent = (ei: number) => {
  formRel.value.events.splice(ei, 1)
}

const buildVisData = () => {
  const hi = highlightIds.value
  const nodes = graph.value.characters.map(c => {
    const ne = (c.story_events || []).length
    const base = [c.name, ...(c.aliases || []), c.traits, c.note].filter(Boolean).join('\n')
    const title = ne ? `${base}\n—\n人物线事件 ${ne} 条` : base
    return {
      id: c.id,
      label: c.name + (c.role ? `\n${c.role}` : '') + (ne ? `\n·${ne}事件` : ''),
      title,
      color: hi.size && !hi.has(c.id) ? { background: '#e2e8f0', border: '#cbd5e1' } : { background: '#c7d2fe', border: '#6366f1' },
      font: { size: 14 },
    }
  })
  const edges = graph.value.relationships.map(r => {
    const ne = (r.story_events || []).length
    const base = [r.label, r.note].filter(Boolean).join('\n')
    const title = ne ? `${base || '关系'}\n—\n共同经历 ${ne} 条` : base || undefined
    return {
      id: r.id,
      from: r.source_id,
      to: r.target_id,
      label: (r.label || '') + (ne ? ` ·${ne}` : ''),
      title,
      arrows: r.directed ? 'to' : undefined,
      font: { size: 11, align: 'middle' },
    }
  })
  return {
    nodes: new DataSet(nodes),
    edges: new DataSet(edges),
  }
}

const applyFocusFromQuery = () => {
  const fid = route.query.focus
  if (!fid || !network) return
  const id = String(fid)
  if (!graph.value.characters.some(x => x.id === id)) return
  try {
    network.selectNodes([id])
    network.focus(id, {
      scale: 1.12,
      animation: {
        duration: 520,
        easingFunction: 'easeInOutQuad',
      },
    })
  } catch {
    /* vis 偶发 */
  }
}

const redraw = async () => {
  await nextTick()
  if (!netContainer.value) return
  const { nodes, edges } = buildVisData()
  const data = { nodes, edges }
  const options = {
    physics: { stabilization: { iterations: 120 } },
    edges: { smooth: false },
    nodes: {
      shape: 'box',
      margin: { top: 8, right: 10, bottom: 8, left: 10 },
      borderWidth: 2,
    },
    interaction: { hover: true, multiselect: false },
  }
  if (network) {
    network.setData(data)
    network.stabilize()
  } else {
    network = new Network(netContainer.value, data, options)
    network.on('click', params => {
      if (params.edges.length) {
        const rid = String(params.edges[0])
        const r = graph.value.relationships.find(x => x.id === rid)
        if (r) {
          castPane.value = 'edge'
          formRel.value = {
            id: r.id,
            source_id: r.source_id,
            target_id: r.target_id,
            label: r.label || '',
            note: r.note || '',
            directed: r.directed,
            events: mapEventsFromApi(r.story_events),
          }
        }
        return
      }
      if (!params.nodes.length) return
      const id = String(params.nodes[0])
      const c = graph.value.characters.find(x => x.id === id)
      if (c) {
        castPane.value = 'node'
        formChar.value = {
          id: c.id,
          name: c.name,
          aliasesStr: (c.aliases || []).join(', '),
          role: c.role || '',
          traits: c.traits || '',
          note: c.note || '',
          events: mapEventsFromApi(c.story_events),
        }
      }
    })
  }
  await nextTick()
  applyFocusFromQuery()
}

const loadCoverage = async () => {
  covLoading.value = true
  try {
    coverage.value = await bookApi.getCastCoverage(slug)
  } catch {
    coverage.value = null
  } finally {
    covLoading.value = false
  }
}

const focusCastNode = (id: string) => {
  router.replace({ query: { ...route.query, focus: id } })
  void nextTick(() => applyFocusFromQuery())
}

const goChapter = (cid: number) => {
  if (cid <= 0) return
  router.push(`/book/${slug}/chapter/${cid}`)
}

const reload = async () => {
  try {
    const data = await bookApi.getCast(slug)
    graph.value = {
      characters: data.characters || [],
      relationships: data.relationships || [],
    }
    highlightIds.value = new Set()
    searchQ.value = ''
    await redraw()
    await loadCoverage()
  } catch {
    message.error('加载失败')
  }
}

let searchTimer: number | null = null
const onSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = window.setTimeout(async () => {
    const q = searchQ.value.trim()
    if (!q) {
      highlightIds.value = new Set()
      await redraw()
      return
    }
    try {
      const res = await bookApi.searchCast(slug, q)
      const ids = new Set<string>()
      const chList = (res.characters || []) as CastCharacter[]
      const relList = (res.relationships || []) as CastRelationship[]
      chList.forEach(c => ids.add(c.id))
      relList.forEach(r => {
        ids.add(r.source_id)
        ids.add(r.target_id)
      })
      highlightIds.value = ids
      await redraw()
    } catch {
      message.error('检索失败')
    }
  }, 280)
}

const applyCharacter = () => {
  const id = formChar.value.id.trim()
  const name = formChar.value.name.trim()
  if (!id || !name) {
    message.warning('请填写 ID 与姓名')
    return
  }
  const aliases = formChar.value.aliasesStr
    .split(/[,，]/)
    .map(s => s.trim())
    .filter(Boolean)
  const next: CastCharacter = {
    id,
    name,
    aliases,
    role: formChar.value.role.trim(),
    traits: formChar.value.traits.trim(),
    note: formChar.value.note.trim(),
    story_events: normalizeStoryEvents(formChar.value.events),
  }
  const i = graph.value.characters.findIndex(c => c.id === id)
  if (i >= 0) graph.value.characters[i] = next
  else graph.value.characters.push(next)
  void redraw()
  message.success('已写入（记得点保存同步到服务器）')
}

const newCharacter = () => {
  formChar.value = { id: '', name: '', aliasesStr: '', role: '', traits: '', note: '', events: [] }
}

const removeCharacter = () => {
  const id = formChar.value.id.trim()
  if (!id) return
  graph.value.characters = graph.value.characters.filter(c => c.id !== id)
  graph.value.relationships = graph.value.relationships.filter(r => r.source_id !== id && r.target_id !== id)
  newCharacter()
  void redraw()
  message.success('已从图中移除（保存后生效）')
}

const applyRelationship = () => {
  const sid = formRel.value.source_id.trim()
  const tid = formRel.value.target_id.trim()
  if (!sid || !tid) {
    message.warning('请填写起点与终点人物 ID')
    return
  }
  let rid = formRel.value.id.trim()
  if (!rid) rid = `r_${Math.random().toString(36).slice(2, 12)}`
  const next: CastRelationship = {
    id: rid,
    source_id: sid,
    target_id: tid,
    label: formRel.value.label.trim(),
    note: formRel.value.note.trim(),
    directed: formRel.value.directed,
    story_events: normalizeStoryEvents(formRel.value.events),
  }
  const i = graph.value.relationships.findIndex(r => r.id === rid)
  if (i >= 0) graph.value.relationships[i] = next
  else graph.value.relationships.push(next)
  formRel.value.id = rid
  void redraw()
  message.success('关系已写入（记得保存）')
}

const removeRelationship = () => {
  const id = formRel.value.id.trim()
  if (!id) return
  graph.value.relationships = graph.value.relationships.filter(r => r.id !== id)
  void redraw()
  message.success('已移除')
}

const saveAll = async () => {
  saving.value = true
  try {
    await bookApi.putCast(slug, {
      version: 2,
      characters: graph.value.characters,
      relationships: graph.value.relationships,
    })
    message.success('已保存到服务器')
    void loadCoverage()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const goWorkbench = () => {
  router.push(`/book/${slug}/workbench`)
}

watch(
  () => route.query.focus,
  () => {
    void nextTick(() => applyFocusFromQuery())
  }
)

onMounted(async () => {
  await reload()
})

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
  network?.destroy()
  network = null
})
</script>

<style scoped>
.cast-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--app-page-bg, #f0f2f8);
}

.cast-header {
  flex-shrink: 0;
  padding: 12px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--app-border);
  background: #fff;
}

.cast-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.ico {
  font-size: 15px;
}

.cast-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.net-wrap {
  flex: 1;
  min-width: 0;
  min-height: 0;
  background: #fafafa;
  border-right: 1px solid var(--app-border);
}

.cast-side {
  width: min(400px, 42vw);
  flex-shrink: 0;
  padding: 12px;
  overflow: auto;
  background: #fff;
}

.side-form {
  padding-top: 8px;
}

.ev-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: flex-start;
  margin-bottom: 10px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(79, 70, 229, 0.05);
  border: 1px solid rgba(99, 102, 241, 0.12);
}

.ev-id {
  width: 100px;
  flex-shrink: 0;
}

.ev-ch {
  width: 88px;
  flex-shrink: 0;
}

.ev-imp {
  width: 92px;
  flex-shrink: 0;
}

.ev-sum {
  flex: 1 1 100%;
  min-width: 0;
}

.cast-hint {
  margin-top: 12px;
}

.cov-collapse {
  margin-bottom: 10px;
}

.cov-collapse :deep(.n-collapse-item__header) {
  font-weight: 600;
  font-size: 13px;
}

.cov-meta {
  display: block;
  margin-bottom: 10px;
  font-size: 12px;
}

.cov-block {
  margin-bottom: 12px;
}

.cov-block-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 6px;
}

.cov-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  font-size: 13px;
}

.cov-row:last-child {
  border-bottom: none;
}

.cov-row-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.cov-name {
  font-weight: 500;
}

.cov-chapters {
  flex-wrap: wrap;
}

.cov-row-quote {
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.cov-count {
  font-size: 12px;
}
</style>
