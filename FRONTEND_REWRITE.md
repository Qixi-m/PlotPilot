# 书稿工作台 - 前端重构方案

## 技术栈

### 核心框架
- **Vue 3.4+** - Composition API + `<script setup>`
- **TypeScript 5.0+** - 类型安全
- **Vite 5.0+** - 快速开发和构建
- **Naive UI** - 现代化UI组件库

### 状态管理和路由
- **Pinia** - 轻量级状态管理
- **Vue Router 4** - 路由管理

### 工具库
- **Axios** - HTTP客户端
- **VueUse** - Vue组合式工具集
- **Day.js** - 时间处理
- **Marked** - Markdown渲染
- **Highlight.js** - 代码高亮

## 项目结构

```
web-app/
├── src/
│   ├── api/              # API接口封装
│   │   ├── book.ts       # 书目相关API
│   │   ├── chat.ts       # 聊天相关API
│   │   ├── chapter.ts    # 章节相关API
│   │   └── job.ts        # 任务相关API
│   ├── assets/           # 静态资源
│   │   ├── styles/       # 全局样式
│   │   └── images/       # 图片资源
│   ├── components/       # 通用组件
│   │   ├── ChatMessage.vue      # 聊天消息组件
│   │   ├── JsonEditor.vue       # JSON编辑器
│   │   ├── MarkdownRenderer.vue # Markdown渲染器
│   │   ├── ProgressBar.vue      # 进度条
│   │   └── TaskStatus.vue       # 任务状态
│   ├── composables/      # 组合式函数
│   │   ├── useChat.ts    # 聊天逻辑
│   │   ├── useTask.ts    # 任务轮询
│   │   └── useTheme.ts   # 主题切换
│   ├── layouts/          # 布局组件
│   │   ├── DefaultLayout.vue    # 默认布局
│   │   └── WorkbenchLayout.vue  # 工作台布局
│   ├── router/           # 路由配置
│   │   └── index.ts
│   ├── stores/           # Pinia状态管理
│   │   ├── book.ts       # 书目状态
│   │   ├── chat.ts       # 聊天状态
│   │   └── user.ts       # 用户状态
│   ├── types/            # TypeScript类型定义
│   │   ├── api.ts        # API类型
│   │   ├── book.ts       # 书目类型
│   │   └── chat.ts       # 聊天类型
│   ├── utils/            # 工具函数
│   │   ├── request.ts    # Axios封装
│   │   ├── format.ts     # 格式化工具
│   │   └── storage.ts    # 本地存储
│   ├── views/            # 页面组件
│   │   ├── Home.vue      # 首页
│   │   ├── Workbench.vue # 工作台
│   │   ├── Chapter.vue   # 章节编辑
│   │   └── Project.vue   # 项目页
│   ├── App.vue           # 根组件
│   └── main.ts           # 入口文件
├── public/               # 公共资源
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

## 核心功能模块

### 1. 首页 (Home.vue)
**设计风格**：创意活泼，类似Figma
- 大标题 + 渐变背景
- 卡片式书目列表，悬停动画
- 创建书目：大文本框 + 浮动按钮
- 空状态：插画 + 引导文案

**核心功能**：
- 书目列表展示（网格布局）
- 快速创建书目（模态框）
- 搜索和筛选

### 2. 工作台 (Workbench.vue)
**布局**：三栏响应式布局
- 左侧：书目导航 + 章节列表（可折叠）
- 中间：聊天区域 + 快捷操作
- 右侧：设定库编辑器（可折叠）

**核心功能**：
- 实时聊天（WebSocket或轮询）
- Markdown渲染 + 代码高亮
- 任务进度可视化
- JSON编辑器（语法高亮 + 验证）

### 3. 章节编辑 (Chapter.vue)
**设计**：专注写作体验
- 全屏编辑模式
- 实时字数统计
- 自动保存指示
- 审定面板（侧边栏）

**核心功能**：
- 富文本编辑器
- 自动保存（防抖）
- 版本历史
- 快捷键支持

### 4. 项目页 (Project.vue)
**设计**：数据可视化
- 章节进度看板
- 任务执行面板
- 统计图表

**核心功能**：
- 章节管理
- 批量操作
- 导出功能

## UI设计规范

### 色彩系统（创意活泼风格）
```css
/* 主色调 - 活力紫 */
--primary: #7C3AED;
--primary-hover: #6D28D9;
--primary-light: #A78BFA;

/* 辅助色 */
--success: #10B981;
--warning: #F59E0B;
--error: #EF4444;
--info: #3B82F6;

/* 中性色 */
--bg-base: #FFFFFF;
--bg-elevated: #F9FAFB;
--text-primary: #111827;
--text-secondary: #6B7280;
--border: #E5E7EB;

/* 深色模式 */
--dark-bg-base: #111827;
--dark-bg-elevated: #1F2937;
--dark-text-primary: #F9FAFB;
--dark-text-secondary: #9CA3AF;
--dark-border: #374151;
```

### 动画效果
- 页面切换：淡入淡出 + 轻微位移
- 卡片悬停：阴影加深 + 轻微上浮
- 按钮点击：缩放反馈
- 加载状态：骨架屏 + 脉冲动画

### 圆角和阴影
```css
--radius-sm: 8px;
--radius-md: 12px;
--radius-lg: 16px;

--shadow-sm: 0 1px 3px rgba(0,0,0,0.1);
--shadow-md: 0 4px 6px rgba(0,0,0,0.1);
--shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
```

## API集成

### Axios配置
```typescript
// utils/request.ts
import axios from 'axios'
import { useMessage } from 'naive-ui'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器
request.interceptors.request.use(config => {
  // 添加token等
  return config
})

// 响应拦截器
request.interceptors.response.use(
  response => response.data,
  error => {
    const message = useMessage()
    message.error(error.message || '请求失败')
    return Promise.reject(error)
  }
)
```

### API封装示例
```typescript
// api/book.ts
export const bookApi = {
  // 获取书目列表
  getList: () => request.get('/books'),

  // 创建书目
  create: (data: CreateBookDto) =>
    request.post('/jobs/create-book', data),

  // 获取书目详情
  getDetail: (slug: string) =>
    request.get(`/book/${slug}`),

  // 获取设定库
  getBible: (slug: string) =>
    request.get(`/book/${slug}/bible`),

  // 保存设定库
  saveBible: (slug: string, data: Bible) =>
    request.put(`/book/${slug}/bible`, data),
}
```

## 状态管理

### Pinia Store示例
```typescript
// stores/book.ts
import { defineStore } from 'pinia'
import { bookApi } from '@/api/book'

export const useBookStore = defineStore('book', {
  state: () => ({
    books: [] as Book[],
    currentBook: null as Book | null,
    loading: false,
  }),

  actions: {
    async fetchBooks() {
      this.loading = true
      try {
        this.books = await bookApi.getList()
      } finally {
        this.loading = false
      }
    },

    async createBook(data: CreateBookDto) {
      const result = await bookApi.create(data)
      await this.fetchBooks()
      return result
    },
  },
})
```

## 组合式函数

### 任务轮询示例
```typescript
// composables/useTask.ts
import { ref, onUnmounted } from 'vue'
import { jobApi } from '@/api/job'

export function useTaskPolling(jobId: string) {
  const status = ref<TaskStatus>('queued')
  const message = ref('')
  const progress = ref(0)
  let timer: number | null = null

  const startPolling = () => {
    timer = setInterval(async () => {
      const result = await jobApi.getStatus(jobId)
      status.value = result.status
      message.value = result.message

      if (result.status === 'done' || result.status === 'error') {
        stopPolling()
      }
    }, 1000)
  }

  const stopPolling = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onUnmounted(stopPolling)

  return { status, message, progress, startPolling, stopPolling }
}
```

## 开发和部署

### 开发环境
```bash
cd web-app
npm install
npm run dev  # 启动开发服务器（默认端口3000）
```

### 生产构建
```bash
npm run build  # 构建到 dist/ 目录
```

### Vite配置（代理后端API）
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})
```

## 优势对比

### 旧版（Vanilla JS）
- ❌ 代码分散，难以维护
- ❌ 无类型检查，容易出错
- ❌ 手动DOM操作，性能差
- ❌ 无组件化，代码重复
- ❌ 样式混乱，缺少规范

### 新版（Vue 3 + TS）
- ✅ 组件化开发，结构清晰
- ✅ TypeScript类型安全
- ✅ 响应式数据，自动更新
- ✅ 代码复用，易于维护
- ✅ 专业UI库，视觉统一
- ✅ 热更新，开发效率高
- ✅ 构建优化，加载速度快

## 实施计划

### 第1阶段：基础搭建（2小时）
1. 初始化项目，安装依赖
2. 配置路由和状态管理
3. 封装API和工具函数
4. 创建基础布局组件

### 第2阶段：核心页面（3小时）
1. 首页：书目列表 + 创建表单
2. 工作台：三栏布局 + 聊天功能
3. 章节编辑：编辑器 + 自动保存
4. 项目页：章节管理 + 任务面板

### 第3阶段：功能完善（2小时）
1. JSON编辑器（语法高亮）
2. Markdown渲染（代码高亮）
3. 任务进度可视化
4. 响应式适配

### 第4阶段：优化和测试（1小时）
1. 性能优化
2. 错误处理
3. 用户体验优化
4. 端到端测试

## 预期效果

1. **视觉效果**：现代化、专业、活泼
2. **用户体验**：流畅、直观、高效
3. **代码质量**：类型安全、易维护、可扩展
4. **性能**：快速加载、流畅交互
5. **可维护性**：组件化、模块化、文档完善
