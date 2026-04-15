/**
 * Cloudflare Worker — doc-convert API 网关
 *
 * 职责：
 * 1. 处理 CORS 预检请求
 * 2. 将 /doc-convert/api/* 请求反代到 Render 后端
 * 3. 限制请求体大小（100MB Worker 免费层上限，应用层限 50MB）
 */

const BACKEND = 'https://open-convert-api.onrender.com'
const ALLOWED_ORIGIN = 'https://covert.ljhztq.com'

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Accept',
  'Access-Control-Max-Age': '86400',
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url)

    // CORS 预检
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS })
    }

    // 只处理 /doc-convert/api/ 路径
    if (!url.pathname.startsWith('/doc-convert/api/')) {
      return new Response('Not Found', { status: 404 })
    }

    // 构建后端 URL：路径保持一致
    const targetUrl = BACKEND + url.pathname + url.search

    // 转发请求
    const proxyReq = new Request(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : null,
      redirect: 'follow',
    })

    let response
    try {
      response = await fetch(proxyReq)
    } catch (e) {
      return new Response(JSON.stringify({ detail: '后端服务不可用，请稍后重试' }), {
        status: 502,
        headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
      })
    }

    // 在响应头中注入 CORS
    const respHeaders = new Headers(response.headers)
    for (const [k, v] of Object.entries(CORS_HEADERS)) {
      respHeaders.set(k, v)
    }

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: respHeaders,
    })
  },
}
