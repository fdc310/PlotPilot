<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { publishApi, type PlatformInfo, type PublishPreview } from '@/api/publish'
import {
  ArrowBackOutline,
  CloudUploadOutline,
  CheckmarkCircleOutline,
  WarningOutline,
  DownloadOutline,
  GlobeOutline,
} from '@vicons/ionicons5'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const novelId = computed(() => route.params.slug as string)

// 平台数据
const platforms = ref<PlatformInfo[]>([])
const loadingPlatforms = ref(false)
const selectedPlatform = ref('')

// 投稿信息
const synopsis = ref('')
const genre = ref('')
const tags = ref<string[]>([])
const tagInput = ref('')

// 预览
const preview = ref<PublishPreview | null>(null)
const loadingPreview = ref(false)
const exporting = ref(false)

const platformNames: Record<string, string> = {
  qidian: '起点中文网',
  zongheng: '纵横中文网',
  fanqie: '番茄小说',
  jinjiang: '晋江文学城',
  ciweimao: '刺猬猫',
  qimao: '七猫小说',
  tadu: '塔读文学',
}

const platformIcons: Record<string, string> = {
  qidian: '🔴',
  zongheng: '🔵',
  fanqie: '🍅',
  jinjiang: '🌸',
  ciweimao: '🐱',
  qimao: '📖',
  tadu: '📚',
}

const selectedPlatformInfo = computed(() =>
  platforms.value.find(p => p.key === selectedPlatform.value)
)

onMounted(async () => {
  loadingPlatforms.value = true
  try {
    const res = await publishApi.listPlatforms()
    platforms.value = res.data.platforms
  } catch {
    message.warning('获取平台列表失败')
  } finally {
    loadingPlatforms.value = false
  }
})

function addTag() {
  const tag = tagInput.value.trim()
  const maxTags = selectedPlatformInfo.value?.tags_max_count || 5
  if (tag && !tags.value.includes(tag) && tags.value.length < maxTags) {
    tags.value.push(tag)
    tagInput.value = ''
  }
}

function removeTag(index: number) {
  tags.value.splice(index, 1)
}

async function handlePreview() {
  if (!selectedPlatform.value) {
    message.warning('请选择投稿平台')
    return
  }
  loadingPreview.value = true
  try {
    const res = await publishApi.preview({
      novel_id: novelId.value,
      platform: selectedPlatform.value,
      synopsis: synopsis.value,
      genre: genre.value,
      tags: tags.value,
    })
    preview.value = res.data
  } catch (err: any) {
    message.error(`预览失败: ${err?.response?.data?.detail || err?.message}`)
  } finally {
    loadingPreview.value = false
  }
}

async function handleExport() {
  if (!selectedPlatform.value) return
  exporting.value = true
  try {
    const res = await publishApi.exportPackage({
      novel_id: novelId.value,
      platform: selectedPlatform.value,
      synopsis: synopsis.value,
      genre: genre.value,
      tags: tags.value,
    })
    // 下载 ZIP
    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const safeName = (preview.value?.title || 'novel').replace(/[/\\:*?"<>|]/g, '_')
    a.download = `${safeName}_${selectedPlatform.value}_投稿包.zip`
    a.click()
    URL.revokeObjectURL(url)
    message.success('投稿包已下载')
  } catch (err: any) {
    message.error(`导出失败: ${err?.response?.data?.detail || err?.message}`)
  } finally {
    exporting.value = false
  }
}

watch(selectedPlatform, () => {
  preview.value = null
})
</script>

<template>
  <div class="publish-page">
    <!-- 顶部导航 -->
    <div class="publish-header">
      <n-button quaternary @click="router.push(novelId ? `/book/${novelId}/workbench` : '/')">
        <template #icon><n-icon><ArrowBackOutline /></n-icon></template>
        返回
      </n-button>
      <div class="publish-header-title">
        <n-icon size="24"><CloudUploadOutline /></n-icon>
        <span>一键投稿</span>
      </div>
    </div>

    <div class="publish-body">
      <!-- 左侧：平台选择 + 信息 -->
      <div class="publish-left">
        <!-- 平台卡片 -->
        <n-card title="选择平台" :bordered="true">
          <n-spin :show="loadingPlatforms">
            <div class="platform-grid">
              <div
                v-for="p in platforms"
                :key="p.key"
                class="platform-card"
                :class="{ active: selectedPlatform === p.key }"
                @click="selectedPlatform = p.key"
              >
                <span class="platform-icon">{{ platformIcons[p.key] || '📖' }}</span>
                <span class="platform-name">{{ platformNames[p.key] || p.name }}</span>
                <span class="platform-tag">≥{{ p.min_chapter_words }}字/章</span>
              </div>
            </div>
          </n-spin>
        </n-card>

        <!-- 投稿信息 -->
        <n-card v-if="selectedPlatform" title="作品信息" :bordered="true" style="margin-top: 16px">
          <n-form label-placement="top">
            <n-form-item label="作品简介">
              <n-input
                v-model:value="synopsis"
                type="textarea"
                :rows="4"
                :maxlength="selectedPlatformInfo?.max_synopsis_length || 300"
                show-count
                placeholder="留空则使用小说 premise"
              />
            </n-form-item>

            <n-form-item label="作品类型">
              <n-input v-model:value="genre" placeholder="如：玄幻、都市、科幻" />
            </n-form-item>

            <n-form-item label="标签">
              <n-space>
                <n-tag
                  v-for="(tag, i) in tags"
                  :key="i"
                  closable
                  @close="removeTag(i)"
                >
                  {{ tag }}
                </n-tag>
              </n-space>
              <n-input
                v-model:value="tagInput"
                placeholder="输入标签后回车"
                style="margin-top: 8px"
                @keyup.enter="addTag"
                :disabled="tags.length >= (selectedPlatformInfo?.tags_max_count || 5)"
              />
            </n-form-item>
          </n-form>
        </n-card>
      </div>

      <!-- 右侧：预览 + 导出 -->
      <div class="publish-right">
        <n-card v-if="selectedPlatform" title="投稿预览" :bordered="true">
          <n-space vertical>
            <n-button
              type="primary"
              block
              :loading="loadingPreview"
              @click="handlePreview"
            >
              <template #icon><n-icon><GlobeOutline /></n-icon></template>
              校验预览
            </n-button>

            <!-- 预览结果 -->
            <template v-if="preview">
              <n-descriptions :column="1" label-placement="left" bordered size="small">
                <n-descriptions-item label="平台">{{ preview.platform_name }}</n-descriptions-item>
                <n-descriptions-item label="书名">{{ preview.title }}</n-descriptions-item>
                <n-descriptions-item label="作者">{{ preview.author }}</n-descriptions-item>
                <n-descriptions-item label="章节数">{{ preview.chapter_count }}</n-descriptions-item>
                <n-descriptions-item label="总字数">
                  <n-tag type="info">{{ preview.total_words.toLocaleString() }}</n-tag>
                </n-descriptions-item>
                <n-descriptions-item v-if="preview.tags.length" label="标签">
                  <n-space>
                    <n-tag v-for="t in preview.tags" :key="t" size="small">{{ t }}</n-tag>
                  </n-space>
                </n-descriptions-item>
              </n-descriptions>

              <!-- 校验警告 -->
              <n-alert
                v-if="preview.warnings.length"
                type="warning"
                title="校验提醒"
                style="margin-top: 12px"
              >
                <ul style="margin: 0; padding-left: 20px">
                  <li v-for="(w, i) in preview.warnings" :key="i">{{ w }}</li>
                </ul>
              </n-alert>

              <n-alert v-else type="success" style="margin-top: 12px">
                <template #icon><n-icon><CheckmarkCircleOutline /></n-icon></template>
                所有校验通过，可以投稿
              </n-alert>

              <!-- 导出按钮 -->
              <n-button
                type="success"
                size="large"
                block
                :loading="exporting"
                @click="handleExport"
                style="margin-top: 16px"
              >
                <template #icon><n-icon><DownloadOutline /></n-icon></template>
                生成投稿包 (ZIP)
              </n-button>
            </template>
          </n-space>
        </n-card>

        <!-- 投稿指南 -->
        <n-card v-if="selectedPlatform" title="投稿指南" :bordered="true" style="margin-top: 16px">
          <div class="guide-content">
            <template v-if="selectedPlatform === 'qidian'">
              <p><strong>起点中文网投稿步骤：</strong></p>
              <ol>
                <li>登录 <a href="https://author.qidian.com" target="_blank">author.qidian.com</a> 作家专区</li>
                <li>点击「创建作品」，填写书名、类型、简介</li>
                <li>进入「作品管理」→「新增章节」</li>
                <li>将投稿包中 chapters/ 目录下的章节逐章粘贴</li>
                <li>建议首次上传 3-5 章，每章 2000-3000 字</li>
              </ol>
            </template>
            <template v-else-if="selectedPlatform === 'fanqie'">
              <p><strong>番茄小说投稿步骤：</strong></p>
              <ol>
                <li>下载番茄小说 APP 或访问 writer.fanqie.com</li>
                <li>注册成为作者，创建新作品</li>
                <li>参考 metadata.json 填写作品信息</li>
                <li>逐章上传章节内容（番茄格式宽松，直接粘贴正文）</li>
                <li>保持每日更新有助于获得推荐</li>
              </ol>
            </template>
            <template v-else>
              <p>投稿包内含详细的操作指南（投稿指南.txt），请按步骤操作。</p>
            </template>
          </div>
        </n-card>

        <!-- 未选择平台提示 -->
        <n-card v-if="!selectedPlatform" :bordered="true">
          <n-empty description="请先选择投稿平台" style="padding: 48px 0">
            <template #icon>
              <n-icon size="48"><CloudUploadOutline /></n-icon>
            </template>
          </n-empty>
        </n-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.publish-page {
  min-height: 100vh;
  background: var(--app-bg, #f8f9fc);
}

.publish-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: var(--app-surface, #fff);
  border-bottom: 1px solid var(--app-border, #e5e7eb);
}

.publish-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text, #1f2937);
}

.publish-body {
  display: flex;
  gap: 24px;
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.publish-left {
  flex: 1;
  min-width: 0;
}

.publish-right {
  width: 400px;
  flex-shrink: 0;
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.platform-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px 12px;
  border: 2px solid var(--app-border, #e5e7eb);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.platform-card:hover {
  border-color: var(--app-primary, #4f46e5);
  background: var(--app-primary-bg, #eef2ff);
}

.platform-card.active {
  border-color: var(--app-primary, #4f46e5);
  background: var(--app-primary-bg, #eef2ff);
  box-shadow: 0 0 0 1px var(--app-primary, #4f46e5);
}

.platform-icon {
  font-size: 28px;
}

.platform-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text, #1f2937);
}

.platform-tag {
  font-size: 11px;
  color: var(--app-text-3, #9ca3af);
}

.guide-content ol {
  padding-left: 20px;
}

.guide-content li {
  margin-bottom: 6px;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .publish-body {
    flex-direction: column;
  }
  .publish-right {
    width: 100%;
  }
}
</style>
