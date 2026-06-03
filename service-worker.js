self.addEventListener('install', (e) => {
  console.log('PWA Service Worker Installed');
});

self.addEventListener('fetch', (e) => {
  // Αφήνει τα αιτήματα να περνάνε κανονικά στον Flask server
  e.respondWith(fetch(e.request));
});