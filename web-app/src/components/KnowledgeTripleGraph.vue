<template>
  <div class="ktg-root">
    <div class="ktg-toolbar">
      <n-text depth="3" class="ktg-hint">
        由 <code>novel_knowledge.facts</code> 三元组生成可视化：节点为实体，边为谓词；悬停可看备注与章号。与叙事页「知识三元组」同源。
      </n-text>
      <n-space :size="8">
        <n-button size="small" quaternary :loading="loading" @click="reload">刷新</n-button>
      </n-space>
    </div>
    <div v-if="emptyHint" class="ktg-empty">
      <n-empty description="尚无三元组，可在「叙事与知识」中填写或由 kg_upsert_fact 写入" size="small" />
    </div>
    <div ref="containerRef" class="ktg-canvas" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import 'vis-network/styles/vis-network.css'
import { bookApi } from '../api/book'

const props = defineProps<{ slug: string }>()

interface Fact {
  id: string
  subject: string
  predicate: string
  object: string
  chapter_id?: number | null
  note?: string
}

const containerRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const facts = ref<Fact[]>([])

let network: Network | null = null

const emptyHint = computed(() => facts.value.length === 0 && !loading.value)

const labelToId = new Map<string, string>()
let nextN = 0

const entityId = (raw: string) => {
  const label = (raw || '').trim() || '（空）'
  if (!labelToId.has(label)) {
    labelToId.set(label, `ent_${nextN++}`)
  }
  return labelToId.get(label)!
}

const buildVisData = () => {
  labelToId.clear()
  nextN = 0
  const nodeSeen = new Set<string>()
  const nodes: Array<Record<string, unknown>> = []
  const edges: Array<Record<string, unknown>> = []

  for (const f of facts.value) {
    const sid = entityId(f.subject)
    const oid = entityId(f.object)
    if (!nodeSeen.has(sid)) {
      nodeSeen.add(sid)
      const lab = (f.subject || '').trim() || '（空）'
      nodes.push({
        id: sid,
        label: lab.length > 42 ? `${lab.slice(0, 40)}…` : lab,
        title: lab,
        color: { background: '#e0e7ff', border: '#6366f1' },
        font: { size: 13 },
      })
    }
    if (!nodeSeen.has(oid)) {
      nodeSeen.add(oid)
      const lab = (f.object || '').trim() || '（空）'
      nodes.push({
        id: oid,
        label: lab.length > 42 ? `${lab.slice(0, 40)}…` : lab,
        title: lab,
        color: { background: '#fce7f3', border: '#db2777' },
        font: { size: 13 },
      })
    }
    const pred = (f.predicate || '').trim() || '—'
    const ch = f.chapter_id != null && f.chapter_id >= 1 ? `第${f.chapter_id}章` : ''
    const tip = [pred, f.note, ch].filter(Boolean).join('\n')
    edges.push({
      id: f.id,
      from: sid,
      to: oid,
      label: pred.length > 28 ? `${pred.slice(0, 26)}…` : pred,
      title: tip,
      arrows: 'to',
      font: { size: 11, align: 'middle' },
    })
  }

  return {
    nodes: new DataSet(nodes),
    edges: new DataSet(edges),
  }
}

const redraw = async () => {
  await nextTick()
  if (!containerRef.value) return
  const { nodes, edges } = buildVisData()
  const data = { nodes, edges }
  const options = {
    physics: { stabilization: { iterations: 160 } },
    edges: { smooth: false },
    nodes: {
      shape: 'box',
      margin: { top: 6, right: 8, bottom: 6, left: 8 },
      borderWidth: 2,
    },
    interaction: { hover: true, multiselect: false },
  }
  if (network) {
    network.setData(data)
    network.stabilize()
    network.fit({ animation: false })
  } else {
    network = new Network(containerRef.value, data, options)
  }
}

const reload = async () => {
  loading.value = true
  try {
    const res = await bookApi.getKnowledge(props.slug)
    facts.value = (res.facts || []) as Fact[]
    await redraw()
  } finally {
    loading.value = false
  }
}

watch(
  () => props.slug,
  () => {
    network?.destroy()
    network = null
    void reload()
  }
)

onMounted(async () => {
  await nextTick()
  await reload()
})

onUnmounted(() => {
  network?.destroy()
  network = null
})
</script>

<style scoped>
.ktg-root {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  background: #fafafa;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  overflow: hidden;
}

.ktg-toolbar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  background: #fff;
}

.ktg-hint {
  font-size: 11px;
  line-height: 1.45;
  max-width: min(100%, 420px);
}

.ktg-hint code {
  font-size: 10px;
  padding: 0 4px;
  border-radius: 4px;
  background: rgba(79, 70, 229, 0.08);
  color: #4338ca;
}

.ktg-canvas {
  flex: 1;
  min-height: 260px;
  width: 100%;
}

.ktg-empty {
  position: absolute;
  left: 0;
  right: 0;
  top: 48px;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 1;
}
</style>
