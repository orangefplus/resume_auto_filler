// Background Service Worker：处理侧栏打开、消息转发、与后端 API 通信。
const DEFAULT_BACKEND = 'http://127.0.0.1:8765';

let cachedBackend = DEFAULT_BACKEND;

// 启动时从 storage 读取后端地址
chrome.storage.local.get(['backend_url'], (data) => {
  if (data && data.backend_url) cachedBackend = data.backend_url;
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.backend_url) {
    cachedBackend = changes.backend_url.newValue || DEFAULT_BACKEND;
  }
});

// 点击扩展图标 → 打开侧边栏
chrome.action.onClicked.addListener(async (tab) => {
  try {
    await chrome.sidePanel.open({ tabId: tab.id });
  } catch (e) {
    console.error('[RAF bg] open side panel failed:', e);
  }
});

// 侧栏 → 后端 / 内容脚本的消息路由
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (!msg || !msg.type) {
        sendResponse({ ok: false, error: 'empty message' });
        return;
      }

      // 侧栏发来"提取字段"
      if (msg.type === 'RAF_BACKEND_EXTRACT') {
        const tabId = msg.tabId;
        const resp = await chrome.tabs.sendMessage(tabId, { type: 'RAF_EXTRACT' });
        sendResponse(resp);
        return;
      }

      // 侧栏发来"执行填写"
      if (msg.type === 'RAF_BACKEND_EXECUTE') {
        const tabId = msg.tabId;
        const resp = await chrome.tabs.sendMessage(tabId, {
          type: 'RAF_EXECUTE',
          plan: msg.plan,
          files: msg.files || [],
        });
        sendResponse(resp);
        return;
      }

      // 侧栏发来"调用后端 /api/fill"
      if (msg.type === 'RAF_BACKEND_FILL') {
        const url = (msg.backend || cachedBackend).replace(/\/+$/, '') + '/api/fill';
        const r = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(msg.payload),
        });
        const data = await r.json();
        sendResponse({ ok: true, data });
        return;
      }

      // 侧栏发来"健康检查"
      if (msg.type === 'RAF_BACKEND_HEALTH') {
        const url = (msg.backend || cachedBackend).replace(/\/+$/, '') + '/api/health';
        try {
          const r = await fetch(url);
          const data = await r.json();
          sendResponse({ ok: true, data });
        } catch (e) {
          sendResponse({ ok: false, error: '无法连接后端：' + (e && e.message ? e.message : e) });
        }
        return;
      }

      // 侧栏发来"保存/读取后端地址"
      if (msg.type === 'RAF_GET_BACKEND') {
        sendResponse({ ok: true, backend: cachedBackend });
        return;
      }
      if (msg.type === 'RAF_SET_BACKEND') {
        const v = (msg.backend || '').trim() || DEFAULT_BACKEND;
        await chrome.storage.local.set({ backend_url: v });
        cachedBackend = v;
        sendResponse({ ok: true, backend: v });
        return;
      }

      sendResponse({ ok: false, error: 'unknown type: ' + msg.type });
    } catch (e) {
      sendResponse({ ok: false, error: String(e && e.message ? e.message : e) });
    }
  })();
  return true;
});
