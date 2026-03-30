<template>
  <div class="cgc-root">
    <div class="cgc-toolbar">
      <n-text depth="3" class="cgc-hint">
        与全页「人物关系网」同源（<code>cast_graph.json</code>）· 侧栏只读预览 · 点节点进入全页编辑
      </n-text>
      <n-space :size="8">
        <n-button size="small" quaternary :loading="loading" @click="reload">同步数据</n-button>
        <n-button size="small" secondary @click="goFull">完整编辑页</n-button>
      </n-space>
    </div>
    <div v-if="emptyHint" class="cgc-empty">
      <n-empty description="尚无人物节点，可在完整页添加" size="small" />
    </div>
    <div ref="containerRef" class="cgc-canvas" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import 'vis-network/styles/vis-network.css'
import { bookApi } from '../api/book'

const props = defineProps<{ slug: string }>()
const router = useRouter()

interface CastCharacter {
  id: string
  name: string
  aliases: string[]
  role: string
  traits: string
  note: string
  story_events?: unknown[]
}

interface CastRelationship {
  id: string
  source_id: string
  target_id: string
  label: string
  note: string
  directed: boolean
  story_events?: unknown[]
}

const containerRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const graph = ref<{ characters: CastCharacter[]; relationships: CastRelationship[] }>({
  characters: [],
  relationships: [],
})

let network: Network | null = null

const emptyHint = computed(() => graph.value.characters.length === 0 && !loading.value)

const buildVisData = () => {
  const nodes = graph.value.characters.map(c => {
    const ne = (c.story_events || []).length
    const base = [c.name, ...(c.aliases || []), c.traits, c.note].filter(Boolean).join('\n')
    return {
      id: c.id,
      label: c.name + (c.role ? `\n${c.role}` : '') + (ne ? `\n·${ne}事件` : ''),
      title: ne ? `${base}\n—\n人物线事件 ${ne} 条` : base,
      color: { background: '#c7d2fe', border: '#6366f1' },
      font: { size: 14 },
    }
  })
  const edges = graph.value.relationships.map(r => {
    const ne = (r.story_events || []).length
    const base = [r.label, r.note].filter(Boolean).join('\n')
    return {
      id: r.id,
      from: r.source_id,
      to: r.target_id,
      label: (r.label || '') + (ne ? ` ·${ne}` : ''),
      title: ne ? `${base || '关系'}\n—\n共同经历 ${ne} 条` : base || undefined,
      arrows: r.directed ? 'to' : undefined,
      font: { size: 11, align: 'middle' },
    }
  })
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
    network = new Network(containerRef.value, data, options)
    network.on('click', params => {
      if (!params.nodes.length) return
      const id = String(params.nodes[0])
      router.push({ path: `/book/${props.slug}/cast`, query: { focus: id } })
    })
  }
}

const reload = async () => {
  loading.value = true
  try {
    const data = await bookApi.getCast(props.slug)
    graph.value = {
      characters: data.characters || [],
      relationships: data.relationships || [],
    }
    await redraw()
  } finally {
    loading.value = false
  }
}

const goFull = () => {
  router.push(`/book/${props.slug}/cast`)
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
.cgc-root {
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

.cgc-toolbar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  background: #fff;
}

.cgc-hint {
  font-size: 11px;
  line-height: 1.45;
  max-width: min(100%, 380px);
}

.cgc-hint code {
  font-size: 10px;
  padding: 0 4px;
  border-radius: 4px;
  background: rgba(79, 70, 229, 0.08);
  color: #4338ca;
}

.cgc-canvas {
  flex: 1;
  min-height: 220px;
  width: 100%;
}

.cgc-empty {
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
