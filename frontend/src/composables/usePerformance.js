import { ref, onMounted, onUnmounted } from 'vue'

/**
 * �����Ż����ʽ����
 * �ṩ��������������ء������������ȹ���
 */

/**
 * ��������
 */
export function useDebounce(fn, delay = 300) {
  let timeoutId = null

  const debouncedFn = (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      fn(...args)
      timeoutId = null
    }, delay)
  }

  const cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  return { debouncedFn, cancel }
}

/**
 * ��������
 */
export function useThrottle(fn, delay = 100) {
  let lastTime = 0
  let timeoutId = null

  const throttledFn = (...args) => {
    const now = Date.now()
    const remaining = delay - (now - lastTime)

    if (remaining <= 0) {
      if (timeoutId) {
        clearTimeout(timeoutId)
        timeoutId = null
      }
      lastTime = now
      fn(...args)
    } else if (!timeoutId) {
      timeoutId = setTimeout(() => {
        lastTime = Date.now()
        timeoutId = null
        fn(...args)
      }, remaining)
    }
  }

  const cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  return { throttledFn, cancel }
}

/**
 * ������ͼƬ
 */
export function useLazyImage(src, options = {}) {
  const { threshold = 0.1, rootMargin = '50px' } = options
  const imageRef = ref(null)
  const isLoaded = ref(false)
  const isError = ref(false)
  const currentSrc = ref('')

  onMounted(() => {
    if (!imageRef.value) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            currentSrc.value = src
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold, rootMargin }
    )

    observer.observe(imageRef.value)

    // ����
    onUnmounted(() => {
      observer.disconnect()
    })
  })

  const onLoad = () => {
    isLoaded.value = true
    isError.value = false
  }

  const onError = () => {
    isLoaded.value = false
    isError.value = true
  }

  return { imageRef, currentSrc, isLoaded, isError, onLoad, onError }
}

/**
 * �������
 */
export function useVirtualScroll(options = {}) {
  const {
    itemHeight = 50,
    overscan = 5,
    containerHeight = 400
  } = options

  const containerRef = ref(null)
  const scrollTop = ref(0)
  const items = ref([])
  const visibleItems = ref([])
  const totalHeight = ref(0)
  const offsetY = ref(0)

  const updateVisibleItems = () => {
    if (!containerRef.value || items.value.length === 0) {
      visibleItems.value = []
      return
    }

    const startIndex = Math.max(0, Math.floor(scrollTop.value / itemHeight) - overscan)
    const endIndex = Math.min(
      items.value.length,
      Math.ceil((scrollTop.value + containerHeight) / itemHeight) + overscan
    )

    visibleItems.value = items.value.slice(startIndex, endIndex).map((item, index) => ({
      ...item,
      index: startIndex + index,
      style: {
        position: 'absolute',
        top: `${(startIndex + index) * itemHeight}px`,
        height: `${itemHeight}px`,
        left: 0,
        right: 0
      }
    }))

    totalHeight.value = items.value.length * itemHeight
    offsetY.value = startIndex * itemHeight
  }

  const onScroll = useThrottle((e) => {
    scrollTop.value = e.target.scrollTop
    updateVisibleItems()
  }, 16) // 60fps

  const setItems = (newItems) => {
    items.value = newItems
    updateVisibleItems()
  }

  return {
    containerRef,
    visibleItems,
    totalHeight,
    offsetY,
    onScroll,
    setItems
  }
}

/**
 * �ڴ滺��
 */
export function useCache(maxSize = 100) {
  const cache = new Map()

  const get = (key) => {
    if (cache.has(key)) {
      const value = cache.get(key)
      // �ƶ������ʹ��
      cache.delete(key)
      cache.set(key, value)
      return value
    }
    return null
  }

  const set = (key, value) => {
    if (cache.has(key)) {
      cache.delete(key)
    } else if (cache.size >= maxSize) {
      // ɾ�����δʹ�õ�
      const firstKey = cache.keys().next().value
      cache.delete(firstKey)
    }
    cache.set(key, value)
  }

  const has = (key) => cache.has(key)

  const remove = (key) => cache.delete(key)

  const clear = () => cache.clear()

  return { get, set, has, remove, clear }
}

/**
 * ����ȥ��
 */
export function useRequestDeduplication() {
  const pendingRequests = new Map()

  const dedupe = async (key, requestFn) => {
    if (pendingRequests.has(key)) {
      return pendingRequests.get(key)
    }

    const promise = requestFn().finally(() => {
      pendingRequests.delete(key)
    })

    pendingRequests.set(key, promise)
    return promise
  }

  return { dedupe }
}

/**
 * ���ܼ��
 */
export function usePerformanceMonitor() {
  const metrics = ref({
    fps: 0,
    memory: 0,
    timing: {}
  })

  let frameCount = 0
  let lastTime = performance.now()
  let animationId = null

  const measureFPS = () => {
    frameCount++
    const currentTime = performance.now()

    if (currentTime - lastTime >= 1000) {
      metrics.value.fps = Math.round((frameCount * 1000) / (currentTime - lastTime))
      frameCount = 0
      lastTime = currentTime
    }

    animationId = requestAnimationFrame(measureFPS)
  }

  const measureMemory = () => {
    if (performance.memory) {
      metrics.value.memory = Math.round(performance.memory.usedJSHeapSize / 1024 / 1024)
    }
  }

  const measureTiming = (name, fn) => {
    const start = performance.now()
    const result = fn()
    const end = performance.now()
    metrics.value.timing[name] = Math.round(end - start)
    return result
  }

  onMounted(() => {
    measureFPS()
    setInterval(measureMemory, 5000)
  })

  onUnmounted(() => {
    if (animationId) {
      cancelAnimationFrame(animationId)
    }
  })

  return { metrics, measureTiming }
}

/**
 * Web Worker ֧��
 */
export function useWorker(workerFn) {
  const worker = ref(null)
  const result = ref(null)
  const error = ref(null)
  const loading = ref(false)

  const createWorker = () => {
    const blob = new Blob([`self.onmessage = ${workerFn.toString()}`], { type: 'application/javascript' })
    worker.value = new Worker(URL.createObjectURL(blob))

    worker.value.onmessage = (e) => {
      result.value = e.data
      loading.value = false
    }

    worker.value.onerror = (e) => {
      error.value = e
      loading.value = false
    }
  }

  const postMessage = (data) => {
    if (!worker.value) createWorker()
    loading.value = true
    error.value = null
    worker.value.postMessage(data)
  }

  const terminate = () => {
    if (worker.value) {
      worker.value.terminate()
      worker.value = null
    }
  }

  onUnmounted(terminate)

  return { result, error, loading, postMessage, terminate }
}

/**
 * ��ԴԤ����
 */
export function usePreload() {
  const preloadedResources = new Set()

  const preloadImage = (src) => {
    if (preloadedResources.has(src)) return Promise.resolve()

    return new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => {
        preloadedResources.add(src)
        resolve()
      }
      img.onerror = reject
      img.src = src
    })
  }

  const preloadScript = (src) => {
    if (preloadedResources.has(src)) return Promise.resolve()

    return new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = src
      script.onload = () => {
        preloadedResources.add(src)
        resolve()
      }
      script.onerror = reject
      document.head.appendChild(script)
    })
  }

  const preloadStyle = (href) => {
    if (preloadedResources.has(href)) return Promise.resolve()

    return new Promise((resolve, reject) => {
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = href
      link.onload = () => {
        preloadedResources.add(href)
        resolve()
      }
      link.onerror = reject
      document.head.appendChild(link)
    })
  }

  return { preloadImage, preloadScript, preloadStyle }
}
