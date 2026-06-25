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

/**
 * 触发文件下载
 */
export function downloadResult(jobId) {
  const url = `${API_BASE}/download/${jobId}`
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)

  // 下载开始后延迟删除文件（给浏览器足够时间开始下载）
  setTimeout(() => deleteJob(jobId), 30000)
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
