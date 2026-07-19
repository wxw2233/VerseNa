import { ref, watch } from 'vue'

const brightness = ref('dark') // 'dark' | 'light'

/**
 * 采样背景图片亮度，设置 data-brightness 属性。
 * 混合背景色 #0a0a18 + 图片 opacity，计算实际视觉亮度。
 */
export function useBrightness() {
  let _imgUrl = ''
  let _opacity = 0.3

  function sample() {
    if (!_imgUrl) {
      setBrightness('dark')
      return
    }
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      // 缩小采样，降低开销
      const size = 32
      const canvas = document.createElement('canvas')
      canvas.width = size
      canvas.height = size
      const ctx = canvas.getContext('2d')

      // 先填背景色 #0a0a18
      ctx.fillStyle = '#0a0a18'
      ctx.fillRect(0, 0, size, size)

      // 再叠加图片（带 opacity）
      ctx.globalAlpha = _opacity
      ctx.drawImage(img, 0, 0, size, size)
      ctx.globalAlpha = 1

      // 采样平均亮度
      const data = ctx.getImageData(0, 0, size, size).data
      let total = 0
      for (let i = 0; i < data.length; i += 4) {
        // sRGB 相对亮度公式
        total += data[i] * 0.2126 + data[i + 1] * 0.7152 + data[i + 2] * 0.0722
      }
      const avg = total / (data.length / 4)
      setBrightness(avg > 100 ? 'light' : 'dark')
    }
    img.onerror = () => setBrightness('dark')
    img.src = _imgUrl
  }

  function setBrightness(val) {
    brightness.value = val
    document.documentElement.dataset.brightness = val
  }

  /**
   * 更新背景图 URL 和 opacity，触发重新采样
   */
  function update(imgUrl, opacity) {
    _imgUrl = imgUrl || ''
    _opacity = parseFloat(opacity) || 0.3
    sample()
  }

  return { brightness, update }
}
