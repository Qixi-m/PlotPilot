<template>
  <div class="bible-panel">
    <header class="bible-hero">
      <div class="bible-hero-main">
        <div class="bible-title-row">
          <h3 class="bible-title">作品设定</h3>
          <n-tag size="small" round :bordered="false" class="bible-badge">Story Bible</n-tag>
        </div>
        <p class="bible-lead">
          全书<strong>世界观与写作公约</strong>的权威快照：会进入结构规划、章纲与对话上下文。与「梗概」「编务叙事」「人物关系网」分工如下，避免混写。
        </p>
        <div class="bible-roles" aria-label="资料分工">
          <div class="bible-role-item">
            <span class="bible-role-k">梗概 / 主线</span>
            <span class="bible-role-v">manifest · 立项时定调</span>
          </div>
          <div class="bible-role-item bible-role-here">
            <span class="bible-role-k">本书设定</span>
            <span class="bible-role-v">此处 · 文风、人物卡、地点轴</span>
          </div>
          <div class="bible-role-item">
            <span class="bible-role-k">章级编务</span>
            <span class="bible-role-v">叙事侧栏 · 节拍与摘要</span>
          </div>
          <div class="bible-role-item">
            <span class="bible-role-k">人物关系</span>
            <span class="bible-role-v">关系图页 · 节点与边</span>
          </div>
        </div>
        <div class="bible-stats" aria-live="polite">
          <span class="bible-stat"><em>{{ stats.namedChars }}</em> 人物</span>
          <span class="bible-stat-dot" />
          <span class="bible-stat"><em>{{ stats.namedLocs }}</em> 地点/势力</span>
          <span class="bible-stat-dot" />
          <span class="bible-stat"><em>{{ stats.timelineItems }}</em> 时间线</span>
          <span class="bible-stat-dot" />
          <span class="bible-stat bible-stat-style" :class="{ 'is-done': stats.styleOk }">
            文风公约 {{ stats.styleOk ? '已填' : '待补充' }}
          </span>
        </div>
      </div>
      <n-space class="bible-hero-actions" :size="8" align="center">
        <n-button size="small" quaternary @click="showJson = !showJson">
          {{ showJson ? '返回表单' : '高级 · JSON' }}
        </n-button>
        <n-button size="small" type="primary" :loading="saving" @click="save">保存设定</n-button>
      </n-space>
    </header>

    <n-scrollbar class="bible-scroll">
      <div v-if="showJson" class="bible-json-wrap">
        <n-alert type="default" class="bible-json-alert" :bordered="false">
          直接编辑 <code>bible.json</code> 等价结构；保存会覆盖下方表单。须可被后端 Bible 模型解析。
        </n-alert>
        <n-input v-model:value="jsonRaw" type="textarea" class="bible-json" placeholder="{ ... }" />
      </div>

      <div v-else class="bible-form">
        <n-card size="small" class="bible-card" :bordered="false" :segmented="{ content: true, footer: false }">
          <template #header>
            <div class="bcard-head">
              <span class="bcard-icon bcard-icon-text" aria-hidden="true">文</span>
              <div>
                <div class="bcard-title">叙事与风格公约</div>
                <div class="bcard-desc">人称、时态、叙事距离、基调与禁区——全书的「怎么写」。</div>
              </div>
            </div>
          </template>
          <n-input
            v-model:value="state.style_notes"
            type="textarea"
            :autosize="{ minRows: 5, maxRows: 22 }"
            placeholder="建议写明：第三人称有限 / 全知；冷幽默或克制；是否允许破墙、血腥、感情线尺度；参考气质（勿抄原文）…"
            show-count
            :maxlength="12000"
            class="bible-textarea"
          />
        </n-card>

        <n-card size="small" class="bible-card" :bordered="false" :segmented="{ content: true, footer: false }">
          <template #header>
            <div class="bcard-head">
              <span class="bcard-icon" aria-hidden="true">◆</span>
              <div>
                <div class="bcard-title">核心人物卡</div>
                <div class="bcard-desc">姓名、戏内定位、辨识度与成长线；精细关系边请至「人物关系网」维护。</div>
              </div>
            </div>
          </template>
          <n-space vertical class="w-full" :size="14">
            <n-empty
              v-if="!state.characters.length"
              description="尚未添加人物"
              size="small"
              class="bible-empty"
            >
              <template #extra>
                <n-button size="small" dashed @click="addChar">添加第一位人物</n-button>
              </template>
            </n-empty>
            <div v-for="(c, i) in state.characters" :key="i" class="char-block">
              <div class="char-block-head">
                <span class="char-label">人物 {{ i + 1 }}</span>
                <n-button size="tiny" quaternary type="error" @click="removeChar(i)">移除</n-button>
              </div>
              <n-grid :cols="1" :x-gap="12" :y-gap="8">
                <n-gi>
                  <n-form-item label="姓名 / 称呼" label-placement="top" :show-feedback="false">
                    <n-input v-model:value="c.name" placeholder="正文与关系图共用的主称呼" />
                  </n-form-item>
                </n-gi>
                <n-gi>
                  <n-form-item label="戏内定位" label-placement="top" :show-feedback="false">
                    <n-input v-model:value="c.role" placeholder="如：视角主角、反派、导师型配角…" />
                  </n-form-item>
                </n-gi>
                <n-gi>
                  <n-form-item label="辨识度" label-placement="top" :show-feedback="false">
                    <n-input
                      v-model:value="c.traits"
                      type="textarea"
                      :autosize="{ minRows: 2, maxRows: 6 }"
                      placeholder="性格、口癖、外貌或行为习惯，便于撰稿保持一致"
                    />
                  </n-form-item>
                </n-gi>
                <n-gi>
                  <n-form-item label="弧光 / 本卷要完成的转变" label-placement="top" :show-feedback="false">
                    <n-input
                      v-model:value="c.arc_note"
                      type="textarea"
                      :autosize="{ minRows: 2, maxRows: 6 }"
                      placeholder="心理或处境上计划发生的变化，可与大纲对读"
                    />
                  </n-form-item>
                </n-gi>
              </n-grid>
            </div>
            <n-button v-if="state.characters.length" dashed block @click="addChar">+ 添加人物</n-button>
          </n-space>
        </n-card>

        <n-card size="small" class="bible-card" :bordered="false" :segmented="{ content: true, footer: false }">
          <template #header>
            <div class="bcard-head">
              <span class="bcard-icon" aria-hidden="true">◇</span>
              <div>
                <div class="bcard-title">地点 · 势力 · 场景锚点</div>
                <div class="bcard-desc">反复出现的空间或组织，一句话能拉回画面即可。</div>
              </div>
            </div>
          </template>
          <n-space vertical class="w-full" :size="14">
            <div v-for="(loc, i) in state.locations" :key="i" class="loc-block">
              <div class="char-block-head">
                <span class="char-label">条目 {{ i + 1 }}</span>
                <n-button size="tiny" quaternary type="error" @click="removeLoc(i)">移除</n-button>
              </div>
              <n-input v-model:value="loc.name" placeholder="地名、组织或反复场景名" class="mb-8" />
              <n-input
                v-model:value="loc.description"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 8 }"
                placeholder="氛围、势力归属、在本作中的剧情用途（不必过长）"
              />
            </div>
            <n-button dashed block @click="addLoc">+ 添加地点或势力</n-button>
          </n-space>
        </n-card>

        <n-card size="small" class="bible-card bible-card-last" :bordered="false" :segmented="{ content: true, footer: false }">
          <template #header>
            <div class="bcard-head">
              <span class="bible-icon-timeline" aria-hidden="true" />
              <div>
                <div class="bcard-title">故事时间轴要点</div>
                <div class="bcard-desc">一条一事，帮助对齐因果与伏笔；不必写细纲级流水账。</div>
              </div>
            </div>
          </template>
          <n-dynamic-input
            v-model:value="state.timeline_notes"
            :min="0"
            :on-create="() => ''"
            placeholder="例：第三年冬 · 盟约订立；事件前先可空，随写随补"
          />
        </n-card>
      </div>
    </n-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { bookApi } from '../api/book'

const props = defineProps<{ slug: string }>()
const message = useMessage()

interface BibleCharacter {
  name: string
  role: string
  traits: string
  arc_note: string
}
interface BibleLocation {
  name: string
  description: string
}

const emptyState = () => ({
  characters: [] as BibleCharacter[],
  locations: [] as BibleLocation[],
  timeline_notes: [] as string[],
  style_notes: '',
})

const state = ref(emptyState())
const jsonRaw = ref('')
const showJson = ref(false)
const saving = ref(false)

const stats = computed(() => {
  const namedChars = state.value.characters.filter(c => (c.name || '').trim()).length
  const namedLocs = state.value.locations.filter(l => (l.name || '').trim()).length
  const timelineItems = state.value.timeline_notes.map(s => String(s || '').trim()).filter(Boolean).length
  const styleOk = (state.value.style_notes || '').trim().length >= 20
  return { namedChars, namedLocs, timelineItems, styleOk }
})

const syncJsonFromState = () => {
  jsonRaw.value = JSON.stringify(
    {
      characters: state.value.characters,
      locations: state.value.locations,
      timeline_notes: state.value.timeline_notes,
      style_notes: state.value.style_notes,
    },
    null,
    2
  )
}

const load = async () => {
  try {
    const b = await bookApi.getBible(props.slug)
    state.value = {
      characters: Array.isArray(b.characters)
        ? b.characters.map((x: any) => ({
            name: x.name || '',
            role: x.role || '',
            traits: x.traits || '',
            arc_note: x.arc_note || '',
          }))
        : [],
      locations: Array.isArray(b.locations)
        ? b.locations.map((x: any) => ({
            name: x.name || '',
            description: x.description || '',
          }))
        : [],
      timeline_notes: Array.isArray(b.timeline_notes) ? [...b.timeline_notes] : [],
      style_notes: typeof b.style_notes === 'string' ? b.style_notes : '',
    }
    syncJsonFromState()
  } catch {
    message.error('加载设定失败')
  }
}

const save = async () => {
  saving.value = true
  try {
    let payload: Record<string, unknown>
    if (showJson.value) {
      payload = JSON.parse(jsonRaw.value)
    } else {
      payload = {
        characters: state.value.characters.filter(c => (c.name || '').trim()),
        locations: state.value.locations.filter(l => (l.name || '').trim()),
        timeline_notes: state.value.timeline_notes.map(s => String(s || '').trim()).filter(Boolean),
        style_notes: state.value.style_notes,
      }
    }
    await bookApi.saveBible(props.slug, payload)
    message.success('设定已保存')
    if (showJson.value) {
      await load()
    } else {
      syncJsonFromState()
    }
  } catch (e: any) {
    if (e instanceof SyntaxError) {
      message.error('JSON 格式错误')
    } else {
      message.error(e?.response?.data?.detail || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

const addChar = () => {
  state.value.characters.push({ name: '', role: '', traits: '', arc_note: '' })
}
const removeChar = (i: number) => {
  state.value.characters.splice(i, 1)
}
const addLoc = () => {
  state.value.locations.push({ name: '', description: '' })
}
const removeLoc = (i: number) => {
  state.value.locations.splice(i, 1)
}

watch(showJson, v => {
  if (v) syncJsonFromState()
})

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
.bible-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 12px 10px;
  background: linear-gradient(165deg, #f8fafc 0%, #f1f5f9 55%, #eef2f7 100%);
}

.bible-hero {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 2px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.07);
}

.bible-hero-main {
  min-width: 0;
  flex: 1;
}

.bible-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.bible-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #0f172a;
}

.bible-badge {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: none;
  background: rgba(79, 70, 229, 0.1) !important;
  color: #4338ca !important;
}

.bible-lead {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.65;
  color: #475569;
  max-width: 52em;
}

.bible-lead strong {
  color: #334155;
  font-weight: 600;
}

.bible-roles {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin-bottom: 12px;
}

@media (max-width: 520px) {
  .bible-roles {
    grid-template-columns: 1fr;
  }
}

.bible-role-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.bible-role-item.bible-role-here {
  border-color: rgba(99, 102, 241, 0.35);
  background: rgba(99, 102, 241, 0.06);
}

.bible-role-k {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 0.02em;
}

.bible-role-v {
  font-size: 11px;
  color: #334155;
  line-height: 1.4;
}

.bible-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 4px;
  font-size: 12px;
  color: #64748b;
}

.bible-stat em {
  font-style: normal;
  font-weight: 700;
  color: #0f172a;
  margin-right: 2px;
}

.bible-stat-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #cbd5e1;
  margin: 0 2px;
}

.bible-stat-style.is-done {
  color: #15803d;
}

.bible-hero-actions {
  flex-shrink: 0;
  padding-top: 2px;
}

.bible-scroll {
  flex: 1;
  min-height: 0;
}

.bible-form {
  padding: 14px 2px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bible-card {
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  border: 1px solid rgba(15, 23, 42, 0.06) !important;
  background: #fff !important;
}

.bible-card :deep(.n-card-header) {
  padding: 12px 14px 10px;
}

.bible-card :deep(.n-card__content) {
  padding: 12px 14px 14px;
}

.bcard-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.bcard-icon {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  margin-top: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #6366f1;
  background: rgba(99, 102, 241, 0.12);
  border-radius: 6px;
}

.bcard-icon-text {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.bible-icon-timeline {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  margin-top: 2px;
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(14, 165, 233, 0.15));
  position: relative;
}

.bible-icon-timeline::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 5px;
  bottom: 5px;
  width: 2px;
  transform: translateX(-50%);
  border-radius: 1px;
  background: #6366f1;
}

.bcard-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.02em;
  margin-bottom: 4px;
}

.bcard-desc {
  font-size: 11px;
  line-height: 1.5;
  color: #64748b;
}

.bible-textarea :deep(textarea) {
  line-height: 1.55;
}

.char-block,
.loc-block {
  padding: 12px 0;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.char-block:last-child,
.loc-block:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.char-block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.char-label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.mb-8 {
  margin-bottom: 8px;
}

.w-full {
  width: 100%;
}

.bible-empty {
  padding: 8px 0 4px;
}

.bible-json-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 2px 20px;
}

.bible-json-alert {
  font-size: 12px;
  line-height: 1.55;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.04) !important;
}

.bible-json-alert code {
  font-size: 11px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(79, 70, 229, 0.1);
  color: #4338ca;
}

.bible-json {
  min-height: 320px;
  font-family: ui-monospace, 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  border-radius: 10px;
}

.bible-card-last {
  margin-bottom: 0;
}
</style>
