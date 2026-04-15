/**
 * HEIC 图片转换工具
 */

/**
 * 如果是 HEIC，尝试在浏览器内转为 JPEG；失败则原样返回
 */
export async function normalizeHeic(file) {
  const isHeic = file.type === 'image/heic' || file.name.toLowerCase().endsWith('.heic')
  if (!isHeic) return file

  try {
    const { default: heicConvert } = await import('heic-convert')
    const buffer = await file.arrayBuffer()
    const jpegBuffer = await heicConvert({
      buffer: new Uint8Array(buffer),
      format: 'JPEG',
      quality: 0.92,
    })
    const newName = file.name.replace(/\.heic$/i, '.jpg')
    return new File([jpegBuffer], newName, { type: 'image/jpeg' })
  } catch {
    // HEIC 转码失败，原样上传，后端兜底
    return file
  }
}
