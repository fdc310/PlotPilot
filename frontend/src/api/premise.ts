import { apiClient } from './config'

export interface PremiseGenerateRequest {
  premise: string
  genre_hint?: string
}

export interface PremiseGenerateResponse {
  title: string
  genre: string
  world_preset: string
  story_structure: string
  pacing_control: string
  writing_style: string
  special_requirements: string
  suggested_chapters: number
  suggested_words_per_chapter: number
}

export const premiseApi = {
  /** AI 一键生成完整书目配置 */
  generate: (req: PremiseGenerateRequest) =>
    apiClient.post<PremiseGenerateResponse>('/premise/generate', req),
}
