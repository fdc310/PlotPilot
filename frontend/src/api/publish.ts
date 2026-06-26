import { apiClient } from './config'

export interface PlatformInfo {
  key: string
  name: string
  max_title_length: number
  min_chapter_words: number
  tags_max_count: number
}

export interface PublishPreview {
  platform: string
  platform_name: string
  title: string
  author: string
  synopsis: string
  chapter_count: number
  total_words: number
  warnings: string[]
  tags: string[]
}

export interface PublishRequest {
  novel_id: string
  platform: string
  synopsis?: string
  genre?: string
  tags?: string[]
  chapter_start?: number
  chapter_end?: number
}

export const publishApi = {
  /** 列出支持的平台 */
  listPlatforms: () =>
    apiClient.get<{ platforms: PlatformInfo[] }>('/publish/platforms'),

  /** 投稿预览（校验） */
  preview: (req: PublishRequest) =>
    apiClient.post<PublishPreview>('/publish/preview', req),

  /** 生成投稿包（返回 Blob） */
  exportPackage: (req: PublishRequest) =>
    apiClient.post('/publish/export', req, { responseType: 'blob' }),

  /** 支持浏览器自动化的平台 */
  listBrowserPlatforms: () =>
    apiClient.get<{ platforms: string[]; notice: string; requirements: string }>('/publish/browser-platforms'),

  /** 浏览器自动化投稿 */
  browserAutoPublish: (req: { novel_id: string; platform: string; cookie_file?: string; headless?: boolean }) =>
    apiClient.post('/publish/browser-auto', req),
}
