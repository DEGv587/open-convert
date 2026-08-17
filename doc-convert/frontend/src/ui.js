import { getFileExt } from './utils/file.js'

/**
 * 转换矩阵：from_ext → 可选目标格式列表
 * 默认配置，会在初始化时从后端获取
 */
let CONVERSION_MAP = {
  pdf:  ['pdf', 'docx', 'pptx', 'png', 'jpg'],  // 添加 pdf 作为第一个选项
  docx: ['pdf', 'pptx', 'png', 'jpg'],
  doc:  ['pdf', 'pptx', 'png', 'jpg'],
  pptx: ['pdf', 'docx', 'png', 'jpg'],
  ppt:  ['pdf', 'docx', 'png', 'jpg'],
  jpg:  ['pdf', 'docx'],
  jpeg: ['pdf', 'docx'],
  png:  ['pdf', 'docx'],
  heic: ['pdf', 'docx'],
}

let FORMAT_LABELS = {
  pdf: 'PDF', docx: 'Word (DOCX)', pptx: 'PPT (PPTX)', png: 'PNG', jpg: 'JPG'
}

// 当前状态
let _state = 'upload' // upload | config | multi-upload | processing | success | error
let _currentJobId = null
let _currentFilename = null
let _stopPolling = null
let _currentFileExt = null  // 记录当前文件扩展名
let _currentToFormat = null  // 记录当前选择的目标格式

const sections = {}
const $ = id => document.getElementById(id)

export async function initUI() {
  // 收集所有 section
  for (const id of ['upload', 'text-editor', 'text-config', 'multi-upload', 'config', 'processing', 'success', 'error']) {
    sections[id] = document.getElementById(`state-${id}`)
  }

  // 从后端获取配置
  try {
    const API_BASE = import.meta.env.VITE_API_BASE || '/doc-convert/api'
    const response = await fetch(`${API_BASE}/config`)
    if (response.ok) {
      const config = await response.json()
      if (config.conversion_matrix) {
        CONVERSION_MAP = config.conversion_matrix
      }
      if (config.format_labels) {
        FORMAT_LABELS = config.format_labels
      }
    }
  } catch (err) {
    console.warn('Failed to load config from backend, using defaults:', err)
  }
}

export function switchState(name) {
  _state = name
  for (const [id, el] of Object.entries(sections)) {
    el.classList.toggle('active', id === name)
  }
}

export function getCurrentState() { return _state }

/**
 * 渲染文件信息 + 可选格式按钮
 */
export function renderConfig(file, onFormatSelect) {
  $('display-file-name').textContent = file.name
  $('display-file-size').textContent = formatBytes(file.size)

  const ext = getFileExt(file.name)
  _currentFileExt = ext
  _currentToFormat = null
  const targets = CONVERSION_MAP[ext] || ['pdf']

  const group = $('format-options')
  group.innerHTML = ''

  // 重置翻译选项
  _resetTranslateSelector()

  for (const fmt of targets) {
    const btn = document.createElement('button')
    btn.className = 'format-btn'
    btn.textContent = FORMAT_LABELS[fmt] || fmt.toUpperCase()
    btn.dataset.fmt = fmt
    btn.onclick = () => {
      group.querySelectorAll('.format-btn').forEach(b => b.classList.remove('selected'))
      btn.classList.add('selected')
      _currentToFormat = fmt
      $('start-convert-btn').disabled = false
      onFormatSelect(fmt)

      // 仅 PDF → PDF 显示翻译选项
      const showTranslate = ext === 'pdf' && fmt === 'pdf'
      $('translate-selector').style.display = showTranslate ? 'flex' : 'none'
      if (!showTranslate) _resetTranslateSelector()
    }
    group.appendChild(btn)
  }

  // PDF 文件默认选中 PDF 格式
  if (ext === 'pdf' && targets.includes('pdf')) {
    const pdfBtn = group.querySelector('[data-fmt="pdf"]')
    if (pdfBtn) {
      pdfBtn.click()
      // 已经选中，不需要再禁用按钮
      return
    }
  }

  $('start-convert-btn').disabled = true
}

function _resetTranslateSelector() {
  const group = $('translate-options')
  if (!group) return

  const buttons = group.querySelectorAll('.format-btn')

  // 默认选中"不翻译"
  buttons.forEach(b => b.classList.remove('selected'))
  const noTranslateBtn = group.querySelector('[data-lang=""]')
  if (noTranslateBtn) noTranslateBtn.classList.add('selected')

  // 绑定翻译按钮单选
  buttons.forEach(btn => {
    btn.onclick = () => {
      buttons.forEach(b => b.classList.remove('selected'))
      btn.classList.add('selected')

      // 选择翻译语言时显示页码范围
      const lang = btn.dataset.lang
      const showPageRange = lang !== ''
      $('page-range-selector').style.display = showPageRange ? 'flex' : 'none'
    }
  })
}

/** 获取当前选中的翻译目标语言，null 表示不翻译 */
export function getSelectedTranslateLang() {
  const group = $('translate-options')
  if (!group) return null
  const selected = group.querySelector('.format-btn.selected')
  const lang = selected?.dataset.lang || ''
  return lang || null
}

/** 获取页码范围，null 表示不限制范围 */
export function getPageRange() {
  if ($('page-range-selector').style.display === 'none') {
    return null
  }
  const startInput = $('page-range-start')
  const endInput = $('page-range-end')
  if (!startInput || !endInput) {
    return null
  }
  let start = parseInt(startInput.value.trim())
  let end = parseInt(endInput.value.trim())
  if (isNaN(start) || isNaN(end)) {
    return null
  }
  // 自动调整：如果起始页 > 结束页，交换
  if (start > end) {
    [start, end] = [end, start]
  }
  return `${start}-${end}`
}

/** 设置 PDF 总页数并更新提示 */
export function setPdfTotalPages(totalPages) {
  const hint = $('page-range-hint')
  const startInput = $('page-range-start')
  const endInput = $('page-range-end')
  if (hint) {
    hint.textContent = `共 ${totalPages} 页`
  }
  if (startInput && endInput) {
    // 设置默认值
    startInput.value = '1'
    endInput.value = Math.min(10, totalPages).toString()
    startInput.max = totalPages
    endInput.max = totalPages
  }
}

/**
 * 进入处理状态
 */
export function enterProcessing(label = '正在上传...') {
  setProcessText(label)
  setProgress(0, false)
  $('stage-text').textContent = ''
  switchState('processing')
}

export function setProcessText(text) {
  $('process-text').textContent = text
}

export function setProgress(pct, indeterminate = false) {
  const fill = $('progress-fill')
  const pctEl = $('progress-pct')
  if (indeterminate) {
    fill.classList.add('indeterminate')
    fill.style.width = ''
    pctEl.textContent = ''
  } else {
    fill.classList.remove('indeterminate')
    fill.style.width = pct + '%'
    pctEl.textContent = pct + '%'
  }
}

export function setStageText(text) {
  $('stage-text').textContent = text || ''
}

export function enterSuccess(jobId, warningMessage = null, filename = null) {
  _currentJobId = jobId
  _currentFilename = filename

  // 显示或隐藏警告信息
  const warningEl = $('success-warning')
  if (warningMessage) {
    warningEl.textContent = warningMessage
    warningEl.style.display = 'block'
  } else {
    warningEl.style.display = 'none'
  }

  switchState('success')
}

export function enterError(msg) {
  $('error-message').textContent = msg || '未知错误，请重试'
  switchState('error')
}

export function getCurrentJobId() { return _currentJobId }
export function getCurrentFilename() { return _currentFilename }

export function setStopPolling(fn) { _stopPolling = fn }
export function stopPolling() { _stopPolling && _stopPolling() }

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}
