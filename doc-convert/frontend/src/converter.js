import * as pdfjsLib from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker

export const API_BASE = import.meta.env.VITE_API_BASE || '/doc-convert/api'

/**
 * 提交转换任务（单文件或多文件）
 * @param {File[]} files
 * @param {string} toFormat
 * @param {string[]|null} fileOrder  - 多文件时文件名顺序
 * @param {function} onUploadProgress - (pct: number) => void
 * @returns {Promise<{job_id: string}>}
 */
export function submitConversion(files, toFormat, fileOrder, onUploadProgress, translateTo = null, pageRange = null) {
  return new Promise((resolve, reject) => {
    const fd = new FormData()
    fd.append('to_format', toFormat)
    if (translateTo) fd.append('translate_to', translateTo)
    if (pageRange) fd.append('translate_page_range', pageRange)

    if (files.length === 1 && !fileOrder) {
      fd.append('file', files[0])
    } else {
      for (const f of files) {
        fd.append('files', f)
      }
      fd.append('file_order', JSON.stringify(fileOrder))
    }

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/convert`)

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onUploadProgress) {
        onUploadProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText)
        if (xhr.status >= 400) {
          reject(new Error(data.detail || `HTTP ${xhr.status}`))
        } else {
          resolve(data)
        }
      } catch {
        reject(new Error('服务器返回格式错误'))
      }
    }

    xhr.onerror = () => reject(new Error('网络错误，请检查连接'))
    xhr.ontimeout = () => reject(new Error('请求超时'))
    xhr.send(fd)
  })
}

/**
 * 提交粘贴文本转换任务。
 * 文本以 UTF-8 multipart 字段传输，公式源文本不会经过浏览器编码转换。
 */
export function submitTextConversion(text, toFormat, onUploadProgress) {
  return new Promise((resolve, reject) => {
    const fd = new FormData()
    fd.append('to_format', toFormat)
    fd.append('text_content', text)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/convert`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onUploadProgress) {
        onUploadProgress(Math.round((e.loaded / e.total) * 100))
      }
    }
    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText)
        if (xhr.status >= 400) {
          reject(new Error(data.detail || `HTTP ${xhr.status}`))
        } else {
          resolve(data)
        }
      } catch {
        reject(new Error('服务器返回格式错误'))
      }
    }
    xhr.onerror = () => reject(new Error('网络错误，请检查连接'))
    xhr.ontimeout = () => reject(new Error('请求超时'))
    xhr.send(fd)
  })
}

/**
 * 轮询任务状态
 */
export function pollStatus(jobId, { onProgress, onDone, onError }) {
  let timer = null
  let stopped = false

  const poll = async () => {
    if (stopped) return
    try {
      const res = await fetch(`${API_BASE}/status/${jobId}`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        onError(new Error(data.detail || `HTTP ${res.status}`))
        return
      }
      const data = await res.json()
      if (data.status === 'done') {
        onDone(data)
        return
      }
      if (data.status === 'error') {
        onError(new Error(data.error || '转换失败'))
        return
      }
      onProgress(data)
      timer = setTimeout(poll, 2000)
    } catch (e) {
      onError(e)
    }
  }

  timer = setTimeout(poll, 1000)
  return () => { stopped = true; clearTimeout(timer) }
}

const SAVE_FILE_TYPES = {
  docx: {
    description: 'Word 文档',
    accept: { 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] },
  },
  pdf: {
    description: 'PDF 文档',
    accept: { 'application/pdf': ['.pdf'] },
  },
  pptx: {
    description: 'PowerPoint 文档',
    accept: { 'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'] },
  },
  zip: {
    description: 'ZIP 压缩文件',
    accept: { 'application/zip': ['.zip'] },
  },
  png: { description: 'PNG 图片', accept: { 'image/png': ['.png'] } },
  jpg: { description: 'JPEG 图片', accept: { 'image/jpeg': ['.jpg', '.jpeg'] } },
}

const DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024
const DOWNLOAD_MAX_RETRIES = 3

function getSavePickerOptions(filename) {
  const safeName = filename || 'converted_file'
  const ext = safeName.split('.').pop().toLowerCase()
  const type = SAVE_FILE_TYPES[ext]
  return {
    suggestedName: safeName,
    ...(type ? { types: [type] } : {}),
  }
}

function parseContentRange(value) {
  const match = /^bytes (\d+)-(\d+)\/(\d+)$/.exec(value || '')
  if (!match) return null
  return { start: Number(match[1]), end: Number(match[2]), total: Number(match[3]) }
}

async function fetchDownloadRange(url, start, end) {
  let lastError
  for (let attempt = 0; attempt < DOWNLOAD_MAX_RETRIES; attempt += 1) {
    try {
      const response = await fetch(url, { headers: { Range: `bytes=${start}-${end}` } })
      if (response.status === 206 || (response.status === 200 && start === 0)) return response
      const data = await response.json().catch(() => ({}))
      const error = new Error(data.detail || `下载失败（HTTP ${response.status}）`)
      if (response.status >= 400 && response.status < 500 && response.status !== 408 && response.status !== 429) {
        error.nonRetryable = true
      }
      lastError = error
    } catch (error) {
      lastError = error
    }
    if (lastError?.nonRetryable) throw lastError
    if (attempt + 1 < DOWNLOAD_MAX_RETRIES) {
      await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)))
    }
  }
  throw lastError || new Error('下载失败')
}

async function saveLargeResponseToHandle(url, handle) {
  const writable = await handle.createWritable()
  try {
    let offset = 0
    let total = null
    while (total === null || offset < total) {
      const end = total === null ? DOWNLOAD_CHUNK_SIZE - 1 : Math.min(total - 1, offset + DOWNLOAD_CHUNK_SIZE - 1)
      const response = await fetchDownloadRange(url, offset, end)

      if (response.status === 200) {
        if (response.body) await response.body.pipeTo(writable)
        else await writable.write(await response.blob())
        return
      }

      const contentRange = parseContentRange(response.headers.get('Content-Range'))
      if (!contentRange || contentRange.start !== offset || contentRange.end < contentRange.start) {
        throw new Error('服务器返回了无效的分段下载响应')
      }
      total = contentRange.total
      const data = new Uint8Array(await response.arrayBuffer())
      const expectedLength = contentRange.end - contentRange.start + 1
      if (data.byteLength !== expectedLength) throw new Error('分段下载内容不完整，请重试')
      await writable.write(data)
      offset = contentRange.end + 1
    }
    await writable.close()
  } catch (error) {
    try { await writable.abort?.() } catch { /* preserve the original download error */ }
    throw error
  }
}

async function fetchLargeDownloadBlob(url) {
  const parts = []
  let offset = 0
  let total = null
  let contentType = 'application/octet-stream'

  while (total === null || offset < total) {
    const end = total === null ? DOWNLOAD_CHUNK_SIZE - 1 : Math.min(total - 1, offset + DOWNLOAD_CHUNK_SIZE - 1)
    const response = await fetchDownloadRange(url, offset, end)
    contentType = response.headers.get('Content-Type') || contentType
    if (response.status === 200) return response.blob()

    const contentRange = parseContentRange(response.headers.get('Content-Range'))
    if (!contentRange || contentRange.start !== offset || contentRange.end < contentRange.start) {
      throw new Error('服务器返回了无效的分段下载响应')
    }
    total = contentRange.total
    const data = await response.arrayBuffer()
    const expectedLength = contentRange.end - contentRange.start + 1
    if (data.byteLength !== expectedLength) throw new Error('分段下载内容不完整，请重试')
    parts.push(data)
    offset = contentRange.end + 1
  }

  return new Blob(parts, { type: contentType })
}

/**
 * 下载转换结果。支持 File System Access API 时优先弹出系统保存位置选择框。
 */
export async function downloadResult(jobId, filename = null) {
  const url = `${API_BASE}/download/${jobId}`

  if (typeof window.showSaveFilePicker === 'function') {
    let handle
    try {
      handle = await window.showSaveFilePicker(getSavePickerOptions(filename))
    } catch (error) {
      if (error?.name === 'AbortError') return false
      throw error
    }

    await saveLargeResponseToHandle(url, handle)
    await deleteJob(jobId)
    return true
  }

  // Safari / Firefox 等尚未支持保存选择框的浏览器回退为分段下载。
  const blob = await fetchLargeDownloadBlob(url)
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename || ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)

  // 给浏览器足够时间读取 Blob，再释放内存并删除服务端文件。
  setTimeout(() => {
    URL.revokeObjectURL(objectUrl)
    deleteJob(jobId)
  }, 30000)
  return true
}

/**
 * 删除任务文件
 */
export async function deleteJob(jobId) {
  try {
    await fetch(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' })
  } catch (e) {
    console.error('Delete job failed:', e)
  }
}

/**
 * 预热后端（页面加载时调用）
 */
export async function warmup() {
  try {
    await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(10000) })
  } catch {
    // 忽略预热失败
  }
}

/**
 * 在浏览器本地获取 PDF 页数（无需上传）
 * @returns {Promise<number|null>} 总页数，失败返回 null
 */
export async function getPdfPageCount(file) {
  try {
    const buffer = await file.arrayBuffer()
    const doc = await pdfjsLib.getDocument({ data: buffer }).promise
    const numPages = doc.numPages
    doc.destroy()
    return numPages
  } catch (error) {
    console.error('解析 PDF 页数失败:', error)
    return null
  }
}

/**
 * 在浏览器本地裁剪 PDF，只保留指定页码范围，生成新的小文件
 * @param {File} file - 原始 PDF
 * @param {number} startPage - 起始页（从 1 开始）
 * @param {number} endPage - 结束页（从 1 开始，含）
 * @returns {Promise<File>} 裁剪后的新 PDF 文件
 */
export async function cropPdfPages(file, startPage, endPage) {
  const { PDFDocument } = await import('pdf-lib')
  const buffer = await file.arrayBuffer()
  const srcDoc = await PDFDocument.load(buffer)
  const totalPages = srcDoc.getPageCount()

  // 收敛到合法范围（转 0 索引）
  const start = Math.max(0, startPage - 1)
  const end = Math.min(totalPages - 1, endPage - 1)
  const indices = []
  for (let i = start; i <= end; i++) indices.push(i)

  const newDoc = await PDFDocument.create()
  const copied = await newDoc.copyPages(srcDoc, indices)
  copied.forEach((page) => newDoc.addPage(page))

  const bytes = await newDoc.save()
  // 文件名加裁剪后缀，保留 .pdf 扩展名
  const baseName = file.name.replace(/\.pdf$/i, '')
  return new File([bytes], `${baseName}_p${startPage}-${endPage}.pdf`, { type: 'application/pdf' })
}
