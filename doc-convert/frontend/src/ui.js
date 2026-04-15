import { getFileExt } from './utils/file.js'

/**
 * 转换矩阵：from_ext → 可选目标格式列表
 * 默认配置，会在初始化时从后端获取
 */
let CONVERSION_MAP = {
  pdf:  ['docx', 'pptx', 'png', 'jpg'],
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
let _stopPolling = null

const sections = {}
const $ = id => document.getElementById(id)

export async function initUI() {
  // 收集所有 section
  for (const id of ['upload', 'multi-upload', 'config', 'processing', 'success', 'error']) {
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
  const targets = CONVERSION_MAP[ext] || ['pdf']

  const group = $('format-options')
  group.innerHTML = ''
  let selected = null

  for (const fmt of targets) {
    const btn = document.createElement('button')
    btn.className = 'format-btn'
    btn.textContent = FORMAT_LABELS[fmt] || fmt.toUpperCase()
    btn.dataset.fmt = fmt
    btn.onclick = () => {
      group.querySelectorAll('.format-btn').forEach(b => b.classList.remove('selected'))
      btn.classList.add('selected')
      selected = fmt
      $('start-convert-btn').disabled = false
      onFormatSelect(fmt)
    }
    group.appendChild(btn)
  }
  $('start-convert-btn').disabled = true
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

export function enterSuccess(jobId) {
  _currentJobId = jobId
  switchState('success')
}

export function enterError(msg) {
  $('error-message').textContent = msg || '未知错误，请重试'
  switchState('error')
}

export function getCurrentJobId() { return _currentJobId }

export function setStopPolling(fn) { _stopPolling = fn }
export function stopPolling() { _stopPolling && _stopPolling() }

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}
