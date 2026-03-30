import axios from 'axios'
import type { GlobalStats, BookStats, ChapterStats, WritingProgress } from '../types/api'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Add response interceptor to extract data
request.interceptors.response.use(response => response.data)

export const statsApi = {
  /**
   * Get global statistics across all books
   * GET /stats/global
   */
  getGlobal: () => request.get<GlobalStats>('/stats/global') as Promise<GlobalStats>,

  /**
   * Get statistics for a specific book
   * GET /stats/book/{slug}
   */
  getBook: (slug: string) => request.get<BookStats>(`/stats/book/${slug}`) as Promise<BookStats>,

  /**
   * Get statistics for a specific chapter
   * GET /stats/book/{slug}/chapter/{chapterId}
   */
  getChapter: (slug: string, chapterId: number) =>
    request.get<ChapterStats>(`/stats/book/${slug}/chapter/${chapterId}`) as Promise<ChapterStats>,

  /**
   * Get writing progress over time
   * GET /stats/book/{slug}/progress
   */
  getProgress: (slug: string, days = 30) =>
    request.get<WritingProgress[]>(`/stats/book/${slug}/progress`, {
      params: { days },
    }) as Promise<WritingProgress[]>,

  /**
   * Fetch book stats and progress in parallel
   * Combines getBook() and getProgress() for efficient data loading
   */
  getBookAllStats: async (slug: string, days = 30) => {
    const [bookStats, progress] = await Promise.all([
      statsApi.getBook(slug),
      statsApi.getProgress(slug, days),
    ])
    return { bookStats, progress }
  },
}
