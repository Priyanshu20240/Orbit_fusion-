/**
 * Debounce utility for minimizing excessive API/tile requests
 * Useful for search, zoom, and pan operations
 */

export const debounce = (func, delay) => {
  let timeoutId
  return (...args) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => func(...args), delay)
  }
}

/**
 * Throttle utility for rate-limiting function execution
 * Useful for scroll/resize/move events
 */
export const throttle = (func, limit) => {
  let inThrottle
  return (...args) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => inThrottle = false, limit)
    }
  }
}

/**
 * Request batching utility for combining multiple tile requests
 * Reduces number of HTTP requests to the server
 */
export class RequestBatcher {
  constructor(batchDelay = 100, maxBatchSize = 10) {
    this.batchDelay = batchDelay
    this.maxBatchSize = maxBatchSize
    this.queue = []
    this.timeoutId = null
    this.callbacks = new Map()
  }

  add(key, request) {
    return new Promise((resolve, reject) => {
      this.queue.push({ key, request })
      this.callbacks.set(key, { resolve, reject })

      if (this.queue.length >= this.maxBatchSize) {
        this.flush()
      } else if (!this.timeoutId) {
        this.timeoutId = setTimeout(() => this.flush(), this.batchDelay)
      }
    })
  }

  flush() {
    if (this.timeoutId) {
      clearTimeout(this.timeoutId)
      this.timeoutId = null
    }

    if (this.queue.length === 0) return

    const batch = this.queue.splice(0, this.maxBatchSize)
    // Process batch
    batch.forEach(({ key, request }) => {
      request()
        .then(result => {
          const callback = this.callbacks.get(key)
          if (callback) callback.resolve(result)
          this.callbacks.delete(key)
        })
        .catch(error => {
          const callback = this.callbacks.get(key)
          if (callback) callback.reject(error)
          this.callbacks.delete(key)
        })
    })

    // Process remaining items if any
    if (this.queue.length > 0) {
      this.timeoutId = setTimeout(() => this.flush(), this.batchDelay)
    }
  }
}

/**
 * Cache utility for client-side caching of API responses
 * Reduces redundant requests and improves performance
 */
export class ClientCache {
  constructor(maxSize = 100, ttl = 3600000) { // 1 hour default
    this.maxSize = maxSize
    this.ttl = ttl
    this.cache = new Map()
    this.accessLog = new Map()
  }

  set(key, value) {
    // Implement LRU eviction if cache is full
    if (this.cache.size >= this.maxSize) {
      const oldestKey = Array.from(this.accessLog.entries())
        .sort((a, b) => a[1] - b[1])[0][0]
      this.cache.delete(oldestKey)
      this.accessLog.delete(oldestKey)
    }

    this.cache.set(key, {
      value,
      timestamp: Date.now()
    })
    this.accessLog.set(key, Date.now())
  }

  get(key) {
    const item = this.cache.get(key)
    if (!item) return null

    // Check if expired
    if (Date.now() - item.timestamp > this.ttl) {
      this.cache.delete(key)
      this.accessLog.delete(key)
      return null
    }

    // Update access time for LRU
    this.accessLog.set(key, Date.now())
    return item.value
  }

  clear() {
    this.cache.clear()
    this.accessLog.clear()
  }
}

export default {
  debounce,
  throttle,
  RequestBatcher,
  ClientCache
}
