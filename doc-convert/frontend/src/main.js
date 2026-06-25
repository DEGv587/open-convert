/**
 * 应用入口：协调各模块
 */
import { warmup, submitConversion, pollStatus, downloadResult, getPdfInfo } from './converter.js'
import { initUploader } from './uploader.js'
import { initMultiUploader, getFileList, getFileOrder, resetMulti, addFiles } from './multi-uploader.js'
import {
  initUI, switchState, renderConfig, getCurrentState,
  enterProcessing, setProcessText, setProgress, setStageText,
  enterSuccess, enterError, getCurrentJobId, setStopPolling, stopPolling,
  getSelectedTranslateLang, getPageRange, setPdfTotalPages,
} from './ui.js'
import { isImageFile } from './utils/file.js'

let selectedFile = null
let selectedFormat = null

// 初始化
;(async () => {
  await initUI()
  warmup()
})()

// --- 单文件上传 ---
initUploader(
  // 单文件回调
  async (file) => {
    selectedFile = file
    selectedFormat = null

    // 如果是 PDF，获取页数
    if (file.name.toLowerCase().endsWith('.pdf')) {
      switchState('processing')
      setProcessText('正在分析 PDF 文件...')
      setStageText('首次访问可能需要 3-5 分钟，请耐心等待')

      // 假进度条：5分钟内从 0% 到 90%
      let progress = 0
      const interval = setInterval(() => {
        progress += 1
        if (progress <= 90) {
          setProgress(progress)
        }
      }, 3333) // 5分钟 = 300秒，90% 需要 300/90*1000 ≈ 3333ms

      const info = await getPdfInfo(file)
      clearInterval(interval)

      if (info && info.total_pages) {
        setPdfTotalPages(info.total_pages)
        setProgress(100)
        setStageText(`分析完成，共 ${info.total_pages} 页`)
        setTimeout(() => {
          renderConfig(file, (fmt) => { selectedFormat = fmt })
          switchState('config')
        }, 500)
      } else {
        renderConfig(file, (fmt) => { selectedFormat = fmt })
        switchState('config')
      }
      return
    }

    // 如果是图片，进入多图模式
    if (isImageFile(file)) {
      resetMulti()
      await addFiles([file])
      switchState('multi-upload')
      return
    }

    renderConfig(file, (fmt) => { selectedFormat = fmt })
    switchState('config')
  },
  // 多文件回调
  async (files) => {
    // 检查是否全是图片
    const allImages = files.every(isImageFile)

    if (allImages) {
      // 全是图片，进入多图模式
      resetMulti()
      await addFiles(files)
      switchState('multi-upload')
    } else {
      // 混合类型或非图片，提示只能单个处理
      alert('请一次只上传一个非图片文件，或多个图片文件合并为 PDF')
    }
  }
)

// --- 事件绑定 ---

// 移除文件
document.getElementById('remove-file-btn').addEventListener('click', reset)

// 开始转换（单文件）
document.getElementById('start-convert-btn').addEventListener('click', () => {
  if (!selectedFile || !selectedFormat) return
  startSingleConversion(selectedFile, selectedFormat)
})

// 多图转换
document.getElementById('multi-convert-btn').addEventListener('click', () => {
  const files = getFileList()
  if (!files.length) {
    alert('请至少添加一张图片')
    return
  }
  startMultiConversion(files, 'pdf')
})

document.getElementById('multi-reset-btn').addEventListener('click', () => {
  resetMulti()
  reset()
})

// 下载
document.getElementById('download-btn').addEventListener('click', () => {
  const jobId = getCurrentJobId()
  if (jobId) downloadResult(jobId)
})

// 成功后重置
document.getElementById('success-reset-btn').addEventListener('click', reset)

// 失败后重试
document.getElementById('retry-btn').addEventListener('click', () => {
  if (selectedFile && selectedFormat) {
    startSingleConversion(selectedFile, selectedFormat)
  } else {
    const files = getFileList()
    if (files.length) startMultiConversion(files, 'pdf')
    else reset()
  }
})

document.getElementById('error-reset-btn').addEventListener('click', reset)

// 多图上传模块初始化
initMultiUploader((files) => {
  // 每次文件列表变更时更新转换按钮状态
  document.getElementById('multi-convert-btn').disabled = files.length === 0
})

// --- 核心逻辑 ---

async function startConversion(files, toFormat, fileOrder = null, processingText = '正在转换...', translateTo = null, pageRange = null) {
  enterProcessing('正在上传...')

  try {
    const { job_id } = await submitConversion(files, toFormat, fileOrder, (pct) => {
      setProgress(Math.round(pct * 0.4))
      setProcessText(`正在上传... ${Math.round(pct * 0.4)}%`)
    }, translateTo, pageRange)

    setProcessText(processingText)
    setProgress(40)

    const stop = pollStatus(job_id, {
      onProgress: (data) => {
        const convPct = data.progress || 0
        const total = 40 + Math.round(convPct * 0.6)
        setProgress(total)
        setStageText(data.stage || '')
      },
      onDone: (data) => {
        stop && stop()

        // 检测部分成功的警告（限额用完）
        let warningMsg = null
        if (data.stage && /限额|部分翻译|API 限额已用完/.test(data.stage)) {
          warningMsg = '⚠️ ' + data.stage
        }

        enterSuccess(job_id, warningMsg)
      },
      onError: (err) => {
        stop && stop()
        enterError(err.message)
      },
    })
    setStopPolling(stop)
  } catch (err) {
    enterError(err.message)
  }
}

async function startSingleConversion(file, toFormat) {
  const translateTo = getSelectedTranslateLang()
  const pageRange = getPageRange()
  const label = translateTo ? '正在转换并翻译...' : '正在转换...'
  await startConversion([file], toFormat, null, label, translateTo, pageRange)
}

async function startMultiConversion(files, toFormat) {
  const fileOrder = getFileOrder()
  await startConversion(files, toFormat, fileOrder, '正在合并为 PDF...')
}

function reset() {
  stopPolling()
  selectedFile = null
  selectedFormat = null
  resetMulti()
  switchState('upload')
}
// 触发前端部署 - Wed Jun 24 18:12:47 CST 2026
