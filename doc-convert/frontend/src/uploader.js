import { normalizeHeic } from './utils/heic.js'

let _onFile = null
let _onFiles = null

export function initUploader(onFile, onFiles) {
  _onFile = onFile
  _onFiles = onFiles
  const dropZone = document.getElementById('drop-zone')
  const fileInput = document.getElementById('file-input')

  dropZone.addEventListener('click', () => fileInput.click())

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault()
    dropZone.classList.add('dragover')
  })
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'))
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault()
    dropZone.classList.remove('dragover')
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) handleFiles(files)
  })

  fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files)
    if (files.length > 0) handleFiles(files)
    fileInput.value = ''
  })
}

async function handleFiles(files) {
  // 检查文件大小
  for (const file of files) {
    if (file.size > 50 * 1024 * 1024) {
      alert(`文件 ${file.name} 大小超过 50MB 限制`)
      return
    }
  }

  // HEIC 前端转码（并行处理）
  const normalized = await Promise.all(files.map(normalizeHeic))

  // 如果只有一个文件，走单文件流程
  if (normalized.length === 1) {
    _onFile && _onFile(normalized[0])
  } else {
    // 多个文件，走多文件流程
    _onFiles && _onFiles(normalized)
  }
}
