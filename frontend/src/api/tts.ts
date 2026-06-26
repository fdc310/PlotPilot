import { apiClient } from './config'

export interface TTSVoice {
  voice_id: string
  name: string
  language: string
  gender: string
  description: string
}

export interface TTSRequest {
  text: string
  voice_id?: string
  rate?: string
  volume?: string
  pitch?: string
}

export const ttsApi = {
  /** 列出可用语音 */
  listVoices: (language = 'zh') =>
    apiClient.get<{ voices: TTSVoice[] }>('/tts/voices', { params: { language } }),

  /** 文本转语音（返回 Blob） */
  synthesize: (req: TTSRequest) =>
    apiClient.post('/tts/synthesize', req, { responseType: 'blob' }),

  /** 整书有声书生成（返回 Blob） */
  synthesizeNovel: (novelId: string, req: { voice_id?: string; rate?: string; chapter_start?: number; chapter_end?: number }) =>
    apiClient.post(`/tts/novel/${novelId}`, req, { responseType: 'blob' }),

  /** 单章语音合成（返回 Blob） */
  synthesizeChapter: (novelId: string, chapterNumber: number, voiceId?: string, rate?: string) =>
    apiClient.post('/tts/chapter', null, {
      params: { novel_id: novelId, chapter_number: chapterNumber, voice_id: voiceId, rate },
      responseType: 'blob',
    }),
}
