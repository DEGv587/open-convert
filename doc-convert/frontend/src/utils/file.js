/**
 * 文件类型判断工具
 */

export const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'heic'])

export function getFileExt(filename) {
  return filename.split('.').pop().toLowerCase()
}

export function isImageFile(file) {
  return IMAGE_EXTS.has(getFileExt(file.name)) || file.type.startsWith('image/')
}

export function isHeicFile(file) {
  return file.type === 'image/heic' || file.name.toLowerCase().endsWith('.heic')
}
