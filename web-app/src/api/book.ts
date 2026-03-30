import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 添加响应拦截器，直接返回数据
request.interceptors.response.use(response => response.data)

export const bookApi = {
  getList: () => request.get('/books') as Promise<any>,
  create: (data: any) => request.post('/jobs/create-book', data) as Promise<{slug: string}>,
  deleteBook: (slug: string) => request.delete(`/book/${slug}`) as Promise<{ ok: boolean }>,
  getCast: (slug: string) =>
    request.get(`/book/${slug}/cast`) as Promise<{
      version: number
      characters: Array<{
        id: string
        name: string
        aliases: string[]
        role: string
        traits: string
        note: string
      }>
      relationships: Array<{
        id: string
        source_id: string
        target_id: string
        label: string
        note: string
        directed: boolean
      }>
    }>,
  putCast: (slug: string, data: unknown) => request.put(`/book/${slug}/cast`, data),
  searchCast: (slug: string, q: string) =>
    request.get(`/book/${slug}/cast/search`, { params: { q } }) as Promise<{
      characters: unknown[]
      relationships: unknown[]
    }>,
  /** 正文与关系图对照：章节出现、设定未入库、书名号未匹配等 */
  getCastCoverage: (slug: string) =>
    request.get(`/book/${slug}/cast/coverage`) as Promise<{
      chapter_files_scanned: number
      characters: Array<{
        id: string
        name: string
        mentioned: boolean
        chapter_ids: number[]
      }>
      bible_not_in_cast: Array<{
        name: string
        role: string
        in_novel_text: boolean
        chapter_ids: number[]
      }>
      quoted_not_in_cast: Array<{ text: string; count: number; chapter_ids: number[] }>
    }>,
  getKnowledge: (slug: string) =>
    request.get(`/book/${slug}/knowledge`) as Promise<{
      version: number
      premise_lock: string
      chapters: Array<{
        chapter_id: number
        summary: string
        key_events: string
        open_threads: string
        consistency_note: string
        beat_sections?: string[]
        sync_status?: string
      }>
      facts: Array<{
        id: string
        subject: string
        predicate: string
        object: string
        chapter_id: number | null
        note: string
      }>
    }>,
  putKnowledge: (slug: string, data: unknown) => request.put(`/book/${slug}/knowledge`, data),
  knowledgeSearch: (slug: string, q: string, k = 6) =>
    request.get(`/book/${slug}/knowledge/search`, { params: { q, k } }) as Promise<{
      ok: boolean
      query: string
      hits: Array<{ id: string | null; text: string; meta: any; distance: number | null }>
    }>,
  getDesk: (slug: string) =>
    request.get(`/book/${slug}/desk`) as Promise<{
      book: {
        title: string
        slug: string
        genre: string
        stage_label: string
        has_bible?: boolean
        has_outline?: boolean
      } | null
      chapters: Array<{
        id: number
        title: string
        has_file: boolean
        one_liner?: string
      }>
    }>,
  getBible: (slug: string) => request.get(`/book/${slug}/bible`) as Promise<any>,
  saveBible: (slug: string, data: unknown) => request.put(`/book/${slug}/bible`, data),
  getChapterBody: (slug: string, chapterId: number) =>
    request.get(`/book/${slug}/chapter/${chapterId}/body`) as Promise<{ content: string; filename: string | null }>,
  saveChapterBody: (slug: string, chapterId: number, content: string) =>
    request.put(`/book/${slug}/chapter/${chapterId}/body`, { content }),
  getChapterReview: (slug: string, chapterId: number) =>
    request.get(`/book/${slug}/chapter/${chapterId}/review`) as Promise<{ status: string; memo: string }>,
  saveChapterReview: (slug: string, chapterId: number, status: string, memo: string) =>
    request.put(`/book/${slug}/chapter/${chapterId}/review`, { status, memo }),
  /** 自动审读：返回 status/memo；save=true 时写入 editorial */
  reviewChapterAi: (slug: string, chapterId: number, save = false) =>
    request.post(`/book/${slug}/chapter/${chapterId}/review-ai`, { save }) as Promise<{
      ok: boolean
      status: string
      memo: string
      saved: boolean
    }>,
  getChapterStructure: (slug: string, chapterId: number) =>
    request.get(`/book/${slug}/chapter/${chapterId}/structure`) as Promise<{
      chapter_id: number
      storage_dir: string | null
      meta: Record<string, unknown> | null
      has_content: boolean
      composite_char_len: number
    }>,
}

export const chatApi = {
  getMessages: (slug: string) => request.get(`/book/${slug}/chat/messages`) as Promise<{ messages: any[] }>,
  /** 非流式；工具模式为多轮 cast/story/kg */
  send: (
    slug: string,
    message: string,
    opts?: {
      use_cast_tools?: boolean
      history_mode?: 'full' | 'fresh'
      clear_thread?: boolean
    }
  ) =>
    request.post(
      `/book/${slug}/chat`,
      {
        message,
        regenerate_digest: false,
        use_cast_tools: opts?.use_cast_tools ?? true,
        history_mode: opts?.history_mode ?? 'full',
        clear_thread: opts?.clear_thread ?? false,
      },
      { timeout: 180000 }
    ) as Promise<{
      ok: boolean
      reply?: string
      llm_enabled?: boolean
      tool_calls?: Array<{ name: string; ok: boolean; detail: string }>
    }>,
  /** 清空 thread.json；digestToo 时同时删 context_digest.md */
  clearThread: (slug: string, digestToo = false) =>
    request.post(`/book/${slug}/chat/clear`, { digest_too: digestToo }) as Promise<{ ok: boolean }>,

  /**
   * SSE：type=chunk 正文片段；type=tool 工具步骤（类 thinking）；type=done 结束；type=error 失败。
   * use_cast_tools=true 时先推送多段 tool，再将正文分块推送。
   */
  sendStream: (
    slug: string,
    message: string,
    opts?: {
      use_cast_tools?: boolean
      history_mode?: 'full' | 'fresh'
      clear_thread?: boolean
    }
  ) => {
    return fetch(`/api/book/${slug}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        regenerate_digest: false,
        use_cast_tools: opts?.use_cast_tools ?? true,
        history_mode: opts?.history_mode ?? 'full',
        clear_thread: opts?.clear_thread ?? false,
      }),
    })
  },
}

export const jobApi = {
  startPlan: (slug: string, dryRun = false, mode: 'initial' | 'revise' = 'initial') =>
    request.post(`/jobs/${slug}/plan`, { dry_run: dryRun, mode }) as Promise<{ job_id: string }>,
  startWrite: (slug: string, from: number, to?: number, dryRun = false, continuity = false) =>
    request.post(`/jobs/${slug}/write`, { from_chapter: from, to_chapter: to, dry_run: dryRun, continuity }) as Promise<{job_id: string}>,
  startRun: (slug: string, dryRun = false, continuity = false) =>
    request.post(`/jobs/${slug}/run`, { dry_run: dryRun, continuity }) as Promise<{job_id: string}>,
  startExport: (slug: string) => request.post(`/jobs/${slug}/export`, {}),
  cancelJob: (jobId: string) => request.post(`/jobs/${jobId}/cancel`, {}) as Promise<{ ok: boolean }>,
  getStatus: (jobId: string) =>
    request.get(`/jobs/${jobId}`) as Promise<{
      status: string
      message?: string
      phase?: string
      error?: string
      done?: boolean
    }>,
}
