// Content Script 入口：响应 sidepanel 的消息，提取 / 注入。
(function () {
  'use strict';

  if (window.__RAF_content_loaded) return;
  window.__RAF_content_loaded = true;

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    (async () => {
      try {
        if (msg && msg.type === 'RAF_EXTRACT') {
          const data = window.__RAF_extract ? window.__RAF_extract() : { fields: [], add_buttons: [] };
          sendResponse({ ok: true, data });
        } else if (msg && msg.type === 'RAF_EXECUTE') {
          if (!window.__RAF_execute) {
            sendResponse({ ok: false, error: 'executor not loaded' });
            return;
          }
          const results = await window.__RAF_execute(msg.plan || {}, msg.files || []);
          sendResponse({ ok: true, results });
        } else if (msg && msg.type === 'RAF_PING') {
          sendResponse({ ok: true, url: location.href, title: document.title });
        } else {
          sendResponse({ ok: false, error: 'unknown message type' });
        }
      } catch (e) {
        sendResponse({ ok: false, error: String(e && e.message ? e.message : e) });
      }
    })();
    // 返回 true 表示异步 sendResponse
    return true;
  });
})();
