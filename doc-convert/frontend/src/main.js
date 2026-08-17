/**
 * 应用入口：协调各模块
 */
import { warmup, submitConversion, submitTextConversion, pollStatus, downloadResult, getPdfPageCount, cropPdfPages, deleteJob } from './converter.js'
import { initUploader } from './uploader.js'
import { initMultiUploader, getFileList, getFileOrder, resetMulti, addFiles } from './multi-uploader.js'
import {
  initUI, switchState, renderConfig, getCurrentState,
  enterProcessing, setProcessText, setProgress, setStageText,
  enterSuccess, enterError, getCurrentJobId, setStopPolling, stopPolling,
  getCurrentFilename, getSelectedTranslateLang, getPageRange, setPdfTotalPages,
} from './ui.js'
import { isImageFile } from './utils/file.js'

// 裁剪后上传的大小上限（留 Worker 100MB 余量）
const MAX_UPLOAD_SIZE = 90 * 1024 * 1024

let selectedFile = null
let selectedFormat = null
let selectedMultiFormat = 'pdf'
let pastedText = ''
let selectedTextFormat = 'docx'

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

    // 如果是 PDF，本地解析页数（无需上传）
    if (file.name.toLowerCase().endsWith('.pdf')) {
      const totalPages = await getPdfPageCount(file)
      if (totalPages) {
        setPdfTotalPages(totalPages)
      }
      renderConfig(file, (fmt) => { selectedFormat = fmt })
      switchState('config')
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

// 粘贴文本：读取剪贴板后进入可编辑文本区
document.getElementById('paste-text-btn').addEventListener('click', async () => {
  let clipboardText = ''
  try {
    if (!navigator.clipboard?.readText) throw new Error('Clipboard API unavailable')
    clipboardText = await navigator.clipboard.readText()
  } catch (error) {
    console.warn('读取剪贴板失败:', error)
    alert('浏览器未授权读取剪贴板，请在文本框中手动粘贴内容')
  }
  pastedText = clipboardText
  document.getElementById('text-editor').value = clipboardText
  switchState('text-editor')
  document.getElementById('text-editor').focus()
})

document.getElementById('text-editor-back-btn').addEventListener('click', reset)

document.getElementById('text-next-btn').addEventListener('click', () => {
  const text = document.getElementById('text-editor').value
  if (!text.trim()) {
    alert('请先粘贴或输入文本')
    return
  }
  pastedText = text
  document.getElementById('text-char-count').textContent = `${text.length.toLocaleString()} 个字符`
  switchState('text-config')
})

document.querySelectorAll('#text-format-options .format-btn').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('#text-format-options .format-btn').forEach((item) => {
      item.classList.toggle('selected', item === button)
    })
    selectedTextFormat = button.dataset.fmt
  })
})

document.getElementById('text-config-back-btn').addEventListener('click', () => {
  document.getElementById('text-editor').value = pastedText
  switchState('text-editor')
  document.getElementById('text-editor').focus()
})

document.getElementById('text-convert-btn').addEventListener('click', () => {
  startTextConversion(pastedText, selectedTextFormat)
})

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
  startMultiConversion(files, selectedMultiFormat)
})

document.querySelectorAll('#multi-format-options .format-btn').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('#multi-format-options .format-btn').forEach((item) => {
      item.classList.toggle('selected', item === button)
    })
    selectedMultiFormat = button.dataset.fmt
  })
})

document.getElementById('multi-reset-btn').addEventListener('click', () => {
  resetMulti()
  reset()
})

// 下载
document.getElementById('download-btn').addEventListener('click', async () => {
  const jobId = getCurrentJobId()
  if (!jobId) return
  const button = document.getElementById('download-btn')
  button.disabled = true
  button.textContent = '正在保存...'
  try {
    await downloadResult(jobId, getCurrentFilename())
  } catch (error) {
    alert(`保存失败：${error.message}`)
  } finally {
    button.disabled = false
    button.textContent = '下载文件'
  }
})

// 成功后重置
document.getElementById('success-reset-btn').addEventListener('click', reset)

// 失败后重试
document.getElementById('retry-btn').addEventListener('click', () => {
  if (selectedFile && selectedFormat) {
    startSingleConversion(selectedFile, selectedFormat)
  } else if (pastedText) {
    startTextConversion(pastedText, selectedTextFormat)
  } else {
    const files = getFileList()
    if (files.length) startMultiConversion(files, selectedMultiFormat)
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

        enterSuccess(job_id, warningMsg, data.filename)
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

async function startTextConversion(text, toFormat) {
  enterProcessing(toFormat === 'pdf' ? '正在生成 PDF...' : '正在生成 Word...')
  try {
    const { job_id } = await submitTextConversion(text, toFormat, (pct) => {
      setProgress(Math.round(pct * 0.4))
      setProcessText(`正在上传文本... ${Math.round(pct * 0.4)}%`)
    })
    setProcessText(toFormat === 'pdf' ? '正在生成 PDF...' : '正在生成 Word...')
    setProgress(40)

    const stop = pollStatus(job_id, {
      onProgress: (data) => {
        const total = 40 + Math.round((data.progress || 0) * 0.6)
        setProgress(total)
        setStageText(data.stage || '')
      },
      onDone: (data) => {
        stop && stop()
        enterSuccess(job_id, null, data.filename)
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

  // PDF 翻译且选了页码范围：本地裁剪，只上传需要的页，避免上传整个大文件
  if (translateTo && pageRange && file.name.toLowerCase().endsWith('.pdf')) {
    const [start, end] = pageRange.split('-').map(Number)
    try {
      enterProcessing('正在提取所选页面...')
      const cropped = await cropPdfPages(file, start, end)
      if (cropped.size > MAX_UPLOAD_SIZE) {
        enterError(`所选页面过大（${Math.round(cropped.size / 1024 / 1024)}MB），请减少翻译页数`)
        return
      }
      // 已裁剪为目标页，后端无需再按页码范围处理
      await startConversion([cropped], toFormat, null, label, translateTo, null)
      return
    } catch (e) {
      console.error('PDF 裁剪失败:', e)
      enterError('提取页面失败，请重试')
      return
    }
  }

  await startConversion([file], toFormat, null, label, translateTo, pageRange)
}

async function startMultiConversion(files, toFormat) {
  const fileOrder = getFileOrder()
  const label = toFormat === 'docx' ? '正在生成 Word 文档...' : '正在合并为 PDF...'
  await startConversion(files, toFormat, fileOrder, label)
}

function reset() {
  stopPolling()
  const jobId = getCurrentJobId()
  if (jobId) deleteJob(jobId)
  selectedFile = null
  selectedFormat = null
  selectedMultiFormat = 'pdf'
  pastedText = ''
  selectedTextFormat = 'docx'
  document.getElementById('text-editor').value = ''
  document.getElementById('text-char-count').textContent = ''
  document.querySelectorAll('#text-format-options .format-btn').forEach((button) => {
    button.classList.toggle('selected', button.dataset.fmt === 'docx')
  })
  document.querySelectorAll('#multi-format-options .format-btn').forEach((button) => {
    button.classList.toggle('selected', button.dataset.fmt === 'pdf')
  })
  resetMulti()
  switchState('upload')
}
// 触发前端部署 - Wed Jun 24 18:12:47 CST 2026
