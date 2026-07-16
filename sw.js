// sw.js —— 轻量 Service Worker
// 作用：把页面外壳（HTML/manifest/图标）缓存到本地，
//       下次打开即使网络慢也能秒开；聊天需要联网时正常走网络。
const CACHE = 'mini-agent-v2';
const STATIC = ['/manifest.webmanifest', '/icon.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(STATIC))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// 这些前缀走网络，绝不缓存（含认证与所有业务 API，避免登录态/数据被陈旧缓存）
const NO_CACHE_PREFIXES = [
  '/auth', '/conversations', '/chat', '/documents', '/connectors',
  '/profile', '/papers', '/schedules', '/sub-agents', '/wrong-questions',
  '/favorites', '/memory', '/account', '/version', '/tools', '/stt',
  '/vision', '/analyze-paper', '/study-plan', '/reset', '/upload',
];

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return; // 只缓存 GET

  const url = new URL(req.url);
  // API 与认证接口：始终走网络，保证登录态和数据实时
  if (NO_CACHE_PREFIXES.some((p) => url.pathname.startsWith(p))) {
    e.respondWith(fetch(req));
    return;
  }

  // 页面导航：始终走网络，保证每次都拿到最新界面；仅在离线且恰好有缓存时回退
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match('/ui') || caches.match('/')));
    return;
  }

  // 静态资源：缓存优先，未命中再走网络
  e.respondWith(
    caches.match(req).then((cached) => cached || fetch(req))
  );
});
