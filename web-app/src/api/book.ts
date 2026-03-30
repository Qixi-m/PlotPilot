import axios from 'axios'
import type {
  BookListItem,
  BookDeskResponse,
  CastGraph,
  CastSearchResponse,
  CastCoverage,
  StoryKnowledge,
  KnowledgeSearchResponse,
  Bible,
  ChapterBody,
  ChapterReview,
  ChapterReviewAiResponse,
  ChapterStructure,
  ChatMessagesResponse,
  ChatResponse,
  SimpleResponse,
  SlugResponse,
  JobCreateResponse,
  JobStatusResponse,
} from '../types/api'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 添加响应拦截器，直接返回数据
request.interceptors.response.use(response => response.data)

export const bookApi = {
  getList: () => request.get<BookListItem[]>('/books') as Promise<BookListItem[]>,
  create: (data: unknown) => request.post<SlugResponse>('/jobs/create-book', data) as Promise<SlugResponse>,
  deleteBook: (slug: string) => request.delete<SimpleResponse>(`/book/${slug}`) as Promise<SimpleResponse>,
  getCast: (slug: string) => request.get<CastGraph>(`/book/${slug}/cast`) as Promise<CastGraph>,
  putCast: (slug: string, data: unknown) => request.put(`/book/${slug}/cast`, data),
  searchCast: (slug: string, q: string) =>
    request.get<CastSearchResponse>(`/book/${slug}/cast/search`, { params: { q } }) as Promise<CastSearchResponse>,
  /** 正文与关系图对照：章节出现、设定未入库、书名号未匹配等 */
  getCastCoverage: (slug: string) =>
    request.get<CastCoverage>(`/book/${slug}/cast/coverage`) as Promise<CastCoverage>,
  getKnowledge: (slug: string) =>
    request.get<StoryKnowledge>(`/book/${slug}/knowledge`) as Promise<StoryKnowledge>,
  putKnowledge: (slug: string, data: unknown) => request.put(`/book/${slug}/knowledge`, data),
  knowledgeSearch: (slug: string, q: string, k = 6) =>
    request.get<KnowledgeSearchResponse>(`/book/${slug}/knowledge/search`, { params: { q, k } }) as Promise<KnowledgeSearchResponse>,
  getDesk: (slug: string) =>
    request.get<BookDeskResponse>(`/book/${slug}/desk`) as Promise<BookDeskResponse>,
  getBible: (slug: string) => request.get<Bible>(`/book/${slug}/bible`) as Promise<Bible>,
  saveBible: (slug: string, data: unknown) => request.put(`/book/${slug}/bible`, data),
  getChapterBody: (slug: string, chapterId: number) =>
    request.get<ChapterBody>(`/book/${slug}/chapter/${chapterId}/body`) as Promise<ChapterBody>,
  saveChapterBody: (slug: string, chapterId: number, content: string) =>
    request.put(`/book/${slug}/chapter/${chapterId}/body`, { content }),
  getChapterReview: (slug: string, chapterId: number) =>
    request.get<ChapterReview>(`/book/${slug}/chapter/${chapterId}/review`) as Promise<ChapterReview>,
  saveChapterReview: (slug: string, chapterId: number, status: string, memo: string) =>
    request.put(`/book/${slug}/chapter/${chapterId}/review`, { status, memo }),
  /** 自动审读：返回 status/memo；save=true 时写入 editorial */
  reviewChapterAi: (slug: string, chapterId: number, save = false) =>
    request.post<ChapterReviewAiResponse>(`/book/${slug}/chapter/${chapterId}/review-ai`, { save }) as Promise<ChapterReviewAiResponse>,
  getChapterStructure: (slug: string, chapterId: number) =>
    request.get<ChapterStructure>(`/book/${slug}/chapter/${chapterId}/structure`) as Promise<ChapterStructure>,
}

export const chatApi = {
  getMessages: (slug: string) => request.get<ChatMessagesResponse>(`/book/${slug}/chat/messages`) as Promise<ChatMessagesResponse>,
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
    request.post<ChatResponse>(
      `/book/${slug}/chat`,
      {
        message,
        regenerate_digest: false,
        use_cast_tools: opts?.use_cast_tools ?? true,
        history_mode: opts?.history_mode ?? 'full',
        clear_thread: opts?.clear_thread ?? false,
      },
      { timeout: 180000 }
    ) as Promise<ChatResponse>,
  /** 清空 thread.json；digestToo 时同时删 context_digest.md */
  clearThread: (slug: string, digestToo = false) =>
    request.post<SimpleResponse>(`/book/${slug}/chat/clear`, { digest_too: digestToo }) as Promise<SimpleResponse>,

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
    request.post<JobCreateResponse>(`/jobs/${slug}/plan`, { dry_run: dryRun, mode }) as Promise<JobCreateResponse>,
  startWrite: (slug: string, from: number, to?: number, dryRun = false, continuity = false) =>
    request.post<JobCreateResponse>(`/jobs/${slug}/write`, { from_chapter: from, to_chapter: to, dry_run: dryRun, continuity }) as Promise<JobCreateResponse>,
  startRun: (slug: string, dryRun = false, continuity = false) =>
    request.post<JobCreateResponse>(`/jobs/${slug}/run`, { dry_run: dryRun, continuity }) as Promise<JobCreateResponse>,
  startExport: (slug: string) => request.post(`/jobs/${slug}/export`, {}),
  cancelJob: (jobId: string) => request.post<SimpleResponse>(`/jobs/${jobId}/cancel`, {}) as Promise<SimpleResponse>,
  getStatus: (jobId: string) =>
    request.get<JobStatusResponse>(`/jobs/${jobId}`) as Promise<JobStatusResponse>,
}
