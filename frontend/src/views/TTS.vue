<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { ttsApi, type TTSVoice } from '@/api/tts'
import {
  PlayOutline,
  PauseOutline,
  DownloadOutline,
  ArrowBackOutline,
  HeadsetOutline,
  VolumeHighOutline,
} from '@vicons/ionicons5'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const novelId = computed(() => route.params.slug as string)

// 语音列表
const voices = ref<TTSVoice[]>([])
const loadingVoices = ref(false)
const selectedVoice = ref('zh-CN-XiaoxiaoNeural')
const rate = ref('+0%')

// 模式：text / chapter / novel
const mode = ref<'text' | 'chapter' | 'novel'>('text')
const inputText = ref('')
const chapterNumber = ref(1)
const chapterStart = ref<number | undefined>(undefined)
const chapterEnd = ref<number | undefined>(undefined)

// 合成状态
const synthesizing = ref(false)
const audioUrl = ref('')
const audioRef = ref<HTMLAudioElement | null>(null)
const isPlaying = ref(false)

const rateOptions = [
  { label: '慢速 (-30%)', value: '-30%' },
  { label: '稍慢 (-15%)', value: '-15%' },
  { label: '正常', value: '+0%' },
  { label: '稍快 (+15%)', value: '+15%' },
  { label: '快速 (+30%)', value: '+30%' },
  { label: '极速 (+50%)', value: '+50%' },
]

const femaleVoices = computed(() => voices.value.filter(v => v.gender === 'female'))
const maleVoices = computed(() => voices.value.filter(v => v.gender === 'male'))

onMounted(async () => {
  loadingVoices.value = true
  try {
    const res = await ttsApi.listVoices('zh')
    voices.value = res.data.voices
  } catch {
    message.warning('获取语音列表失败，使用默认语音')
  } finally {
    loadingVoices.value = false
  }
})

async function handleSynthesize() {
  synthesizing.value = true
  try {
    let blob: Blob

    if (mode.value === 'text') {
      if (!inputText.value.trim()) {
        message.warning('请输入要合成的文本')
        return
      }
      const res = await ttsApi.synthesize({
        text: inputText.value,
        voice_id: selectedVoice.value,
        rate: rate.value,
      })
      blob = res.data
    } else if (mode.value === 'chapter') {
      const res = await ttsApi.synthesizeChapter(
        novelId.value,
        chapterNumber.value,
        selectedVoice.value,
        rate.value,
      )
      blob = res.data
    } else {
      const res = await ttsApi.synthesizeNovel(novelId.value, {
        voice_id: selectedVoice.value,
        rate: rate.value,
        chapter_start: chapterStart.value,
        chapter_end: chapterEnd.value,
      })
      blob = res.data
    }

    // 释放旧 URL
    if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = URL.createObjectURL(blob)
    message.success('语音合成完成')
  } catch (err: any) {
    message.error(`合成失败: ${err?.message || '未知错误'}`)
  } finally {
    synthesizing.value = false
  }
}

function togglePlay() {
  if (!audioRef.value) return
  if (isPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
}

function handleDownload() {
  if (!audioUrl.value) return
  const a = document.createElement('a')
  a.href = audioUrl.value
  a.download = `plotpilot_tts_${Date.now()}.mp3`
  a.click()
}
</script>

<template>
  <div class="tts-page">
    <!-- 顶部导航栏 -->
    <div class="tts-header">
      <n-button quaternary @click="router.push(novelId ? `/book/${novelId}/workbench` : '/')">
        <template #icon><n-icon><ArrowBackOutline /></n-icon></template>
        返回
      </n-button>
      <div class="tts-header-title">
        <n-icon size="24"><HeadsetOutline /></n-icon>
        <span>有声书工坊</span>
      </div>
    </div>

    <div class="tts-body">
      <!-- 左侧：配置面板 -->
      <n-card class="tts-config" title="合成配置" :bordered="true">
        <!-- 模式选择 -->
        <n-form-item label="合成模式">
          <n-radio-group v-model:value="mode">
            <n-radio-button value="text">自由文本</n-radio-button>
            <n-radio-button value="chapter">单章合成</n-radio-button>
            <n-radio-button value="novel">整书有声</n-radio-button>
          </n-radio-group>
        </n-form-item>

        <!-- 自由文本输入 -->
        <template v-if="mode === 'text'">
          <n-form-item label="输入文本">
            <n-input
              v-model:value="inputText"
              type="textarea"
              :rows="6"
              placeholder="在此输入要合成为语音的文本..."
              maxlength="50000"
              show-count
            />
          </n-form-item>
        </template>

        <!-- 章节选择 -->
        <template v-if="mode === 'chapter'">
          <n-form-item label="章节号">
            <n-input-number v-model:value="chapterNumber" :min="1" :max="9999" />
          </n-form-item>
        </template>

        <!-- 整书范围 -->
        <template v-if="mode === 'novel'">
          <n-form-item label="章节范围（可选）">
            <n-space>
              <n-input-number v-model:value="chapterStart" :min="1" placeholder="起始" clearable />
              <span style="line-height: 34px">—</span>
              <n-input-number v-model:value="chapterEnd" :min="1" placeholder="结束" clearable />
            </n-space>
          </n-form-item>
          <n-alert type="info" style="margin-bottom: 16px">
            整书合成耗时较长（每章约 30-60 秒），请耐心等待。
          </n-alert>
        </template>

        <!-- 语音选择 -->
        <n-form-item label="语音角色">
          <n-spin :show="loadingVoices">
            <n-select
              v-model:value="selectedVoice"
              :options="[
                { type: 'group', label: '🎀 女声', key: 'female', children: femaleVoices.map(v => ({ label: v.name, value: v.voice_id })) },
                { type: 'group', label: '🎵 男声', key: 'male', children: maleVoices.map(v => ({ label: v.name, value: v.voice_id })) },
              ]"
              placeholder="选择语音"
              filterable
            />
          </n-spin>
        </n-form-item>

        <!-- 语速 -->
        <n-form-item label="语速">
          <n-select v-model:value="rate" :options="rateOptions" />
        </n-form-item>

        <!-- 合成按钮 -->
        <n-button
          type="primary"
          size="large"
          block
          :loading="synthesizing"
          @click="handleSynthesize"
        >
          <template #icon><n-icon><VolumeHighOutline /></n-icon></template>
          {{ synthesizing ? '正在合成...' : '开始合成' }}
        </n-button>
      </n-card>

      <!-- 右侧：播放器 -->
      <n-card class="tts-player" title="播放器" :bordered="true">
        <div v-if="!audioUrl" class="tts-empty">
          <n-icon size="64" :depth="4"><HeadsetOutline /></n-icon>
          <p>合成完成后在此播放和下载</p>
        </div>

        <template v-else>
          <!-- 音频播放器 -->
          <div class="tts-audio-area">
            <audio
              ref="audioRef"
              :src="audioUrl"
              @play="isPlaying = true"
              @pause="isPlaying = false"
              @ended="isPlaying = false"
              controls
              style="width: 100%"
            />

            <n-space justify="center" style="margin-top: 16px">
              <n-button type="primary" @click="togglePlay">
                <template #icon>
                  <n-icon><component :is="isPlaying ? PauseOutline : PlayOutline" /></n-icon>
                </template>
                {{ isPlaying ? '暂停' : '播放' }}
              </n-button>
              <n-button @click="handleDownload">
                <template #icon><n-icon><DownloadOutline /></n-icon></template>
                下载 MP3
              </n-button>
            </n-space>
          </div>
        </template>

        <!-- 语音介绍 -->
        <n-divider />
        <div class="tts-voice-info">
          <n-descriptions :column="1" label-placement="left" bordered size="small">
            <n-descriptions-item label="当前语音">
              {{ voices.find(v => v.voice_id === selectedVoice)?.name || selectedVoice }}
            </n-descriptions-item>
            <n-descriptions-item label="语速">
              {{ rate === '+0%' ? '正常' : rate }}
            </n-descriptions-item>
          </n-descriptions>
        </div>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.tts-page {
  min-height: 100vh;
  background: var(--app-bg, #f8f9fc);
}

.tts-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: var(--app-surface, #fff);
  border-bottom: 1px solid var(--app-border, #e5e7eb);
}

.tts-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text, #1f2937);
}

.tts-body {
  display: flex;
  gap: 24px;
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.tts-config {
  flex: 1;
  min-width: 0;
}

.tts-player {
  width: 400px;
  flex-shrink: 0;
}

.tts-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: var(--app-text-3, #9ca3af);
  gap: 12px;
}

.tts-audio-area {
  padding: 16px 0;
}

.tts-voice-info {
  margin-top: 8px;
}

@media (max-width: 768px) {
  .tts-body {
    flex-direction: column;
  }
  .tts-player {
    width: 100%;
  }
}
</style>
