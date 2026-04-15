import { isImageFile } from './utils/file.js'
import { normalizeHeic } from './utils/heic.js'

/** @type {File[]} */
let fileList = []
let _onChange = null
let touchDrag = null
const blobUrls = new Set()

const LONG_PRESS_MS = 260
const TOUCH_SLOP_PX = 8
export const MAX_MULTI_FILES = 50

export function initMultiUploader(onChange) {
  _onChange = onChange
  const zone = document.getElementById('multi-drop-zone')

  zone.addEventListener('click', () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.jpg,.jpeg,.png,.heic,image/*'
    input.multiple = true
    input.onchange = () => addFiles(Array.from(input.files))
    input.click()
  })

  zone.addEventListener('dragover', (e) => {
    e.preventDefault()
    zone.classList.add('dragover')
  })
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'))
  zone.addEventListener('drop', (e) => {
    e.preventDefault()
    zone.classList.remove('dragover')
    addFiles(Array.from(e.dataTransfer.files).filter(isImageFile))
  })
}

export async function addFiles(newFiles) {
  // 过滤图片并并行转换 HEIC
  const imageFiles = newFiles.filter(isImageFile)
  const normalized = await Promise.all(imageFiles.map(normalizeHeic))

  // 避免重复文件名
  const existing = new Set(fileList.map(f => f.name))
  for (const f of normalized) {
    if (!existing.has(f.name)) {
      if (fileList.length >= MAX_MULTI_FILES) {
        alert(`最多只能添加 ${MAX_MULTI_FILES} 张图片`)
        break
      }
      fileList.push(f)
      existing.add(f.name)
    }
  }
  renderThumbnails()
  _onChange && _onChange(fileList)
}

function renderThumbnails() {
  const list = document.getElementById('thumbnail-list')
  list.innerHTML = ''

  // 释放旧的 Blob URLs
  blobUrls.forEach(url => URL.revokeObjectURL(url))
  blobUrls.clear()

  fileList.forEach((file, idx) => {
    const card = document.createElement('div')
    card.className = 'thumb-card'
    card.draggable = true
    card.dataset.idx = idx

    const img = document.createElement('img')
    const blobUrl = URL.createObjectURL(file)
    blobUrls.add(blobUrl)
    img.src = blobUrl
    img.alt = file.name
    card.appendChild(img)

    const order = document.createElement('span')
    order.className = 'thumb-order'
    order.textContent = idx + 1
    card.appendChild(order)

    const removeBtn = document.createElement('button')
    removeBtn.className = 'thumb-remove'
    removeBtn.type = 'button'
    removeBtn.textContent = '×'
    removeBtn.setAttribute('aria-label', `移除 ${file.name}`)
    removeBtn.onclick = (e) => {
      e.stopPropagation()
      fileList.splice(idx, 1)
      renderThumbnails()
      _onChange && _onChange(fileList)
    }
    card.appendChild(removeBtn)

    // 拖拽排序
    card.addEventListener('dragstart', (e) => {
      card.classList.add('dragging')
      e.dataTransfer.setData('text/plain', idx)
    })
    card.addEventListener('dragend', () => card.classList.remove('dragging'))
    card.addEventListener('dragover', (e) => {
      e.preventDefault()
      card.classList.add('drag-over')
    })
    card.addEventListener('dragleave', () => card.classList.remove('drag-over'))
    card.addEventListener('drop', (e) => {
      e.preventDefault()
      card.classList.remove('drag-over')
      const fromIdx = parseInt(e.dataTransfer.getData('text/plain'))
      moveFile(fromIdx, idx)
    })

    card.addEventListener('touchstart', (e) => handleTouchStart(e, idx, card), { passive: true })
    card.addEventListener('touchmove', handleTouchMove, { passive: false })
    card.addEventListener('touchend', handleTouchEnd)
    card.addEventListener('touchcancel', clearTouchDrag)

    list.appendChild(card)
  })
}

function moveFile(fromIdx, toIdx) {
  if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0 || fromIdx >= fileList.length || toIdx >= fileList.length) return
  const [moved] = fileList.splice(fromIdx, 1)
  fileList.splice(toIdx, 0, moved)
  renderThumbnails()
  _onChange && _onChange(fileList)
}

export function getFileList() { return [...fileList] }

export function getFileOrder() { return fileList.map(f => f.name) }

export function resetMulti() {
  clearTouchDrag()
  // 释放所有 Blob URLs
  blobUrls.forEach(url => URL.revokeObjectURL(url))
  blobUrls.clear()
  fileList = []
  document.getElementById('thumbnail-list').innerHTML = ''
}

function handleTouchStart(e, idx, card) {
  if (e.touches.length !== 1 || e.target.closest('.thumb-remove')) return

  clearTouchDrag()
  const touch = e.touches[0]
  touchDrag = {
    active: false,
    sourceIdx: idx,
    targetIdx: idx,
    startX: touch.clientX,
    startY: touch.clientY,
    x: touch.clientX,
    y: touch.clientY,
    sourceCard: card,
    ghost: null,
    timer: window.setTimeout(() => activateTouchDrag(), LONG_PRESS_MS),
  }
}

function handleTouchMove(e) {
  if (!touchDrag || e.touches.length !== 1) return

  const touch = e.touches[0]
  touchDrag.x = touch.clientX
  touchDrag.y = touch.clientY

  if (!touchDrag.active) {
    const moved = Math.hypot(touch.clientX - touchDrag.startX, touch.clientY - touchDrag.startY)
    if (moved > TOUCH_SLOP_PX) clearTouchDrag()
    return
  }

  e.preventDefault()
  updateGhostPosition(touch.clientX, touch.clientY)

  const targetCard = document.elementFromPoint(touch.clientX, touch.clientY)?.closest('.thumb-card')
  const targetIdx = targetCard ? Number(targetCard.dataset.idx) : touchDrag.sourceIdx
  updateTouchTarget(targetIdx)
}

function handleTouchEnd() {
  if (!touchDrag) return

  if (!touchDrag.active) {
    clearTouchDrag()
    return
  }

  const { sourceIdx, targetIdx } = touchDrag
  clearTouchDrag()
  moveFile(sourceIdx, targetIdx)
}

function activateTouchDrag() {
  if (!touchDrag) return

  touchDrag.active = true
  touchDrag.sourceCard.classList.add('touch-drag-source')
  document.body.classList.add('touch-dragging')

  const ghost = touchDrag.sourceCard.cloneNode(true)
  ghost.classList.add('touch-drag-ghost')
  ghost.style.width = `${touchDrag.sourceCard.offsetWidth}px`
  ghost.style.height = `${touchDrag.sourceCard.offsetHeight}px`
  document.body.appendChild(ghost)
  touchDrag.ghost = ghost

  updateGhostPosition(touchDrag.x, touchDrag.y)
  updateTouchTarget(touchDrag.sourceIdx)
}

function updateGhostPosition(x, y) {
  if (!touchDrag?.ghost) return
  touchDrag.ghost.style.left = `${x}px`
  touchDrag.ghost.style.top = `${y}px`
}

function updateTouchTarget(targetIdx) {
  if (!touchDrag) return

  const prev = document.querySelector('.thumb-card.touch-drag-target')
  prev && prev.classList.remove('touch-drag-target')

  touchDrag.targetIdx = Number.isInteger(targetIdx) ? targetIdx : touchDrag.sourceIdx
  if (touchDrag.targetIdx === touchDrag.sourceIdx) return

  const next = document.querySelector(`.thumb-card[data-idx="${touchDrag.targetIdx}"]`)
  next && next.classList.add('touch-drag-target')
}

function clearTouchDrag() {
  if (!touchDrag) return

  window.clearTimeout(touchDrag.timer)
  touchDrag.sourceCard?.classList.remove('touch-drag-source')
  document.querySelector('.thumb-card.touch-drag-target')?.classList.remove('touch-drag-target')
  touchDrag.ghost?.remove()
  document.body.classList.remove('touch-dragging')
  touchDrag = null
}
