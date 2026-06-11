// DOM 提取器：在页面里把表单字段抓成 PageField[]。
// 通过 window.__RAF_extract 暴露给 content script 调用。
(function () {
  'use strict';

  const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'META', 'LINK']);
  const FILE_ACCEPT_PREFIXES = ['image/', 'application/pdf', 'application/msword',
                                'application/vnd.openxmlformats-officedocument'];

  /**
   * 为元素生成一个稳定的 CSS selector。
   * 优先 #id > [name] > 路径 + nth-of-type。
   */
  function buildSelector(el) {
    if (el.id && isUniqueSelector(`#${cssEscape(el.id)}`)) {
      return `#${cssEscape(el.id)}`;
    }
    if (el.name) {
      const try1 = `${el.tagName.toLowerCase()}[name="${cssEscape(el.name)}"]`;
      if (isUniqueSelector(try1)) return try1;
    }
    // 构造 nth-of-type 路径
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur.tagName !== 'BODY') {
      let part = cur.tag_NAME || cur.tagName.toLowerCase();
      // tagName 在 html 里是大写
      part = cur.tagName.toLowerCase();
      const parent = cur.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(
          c => c.tagName === cur.tagName
        );
        if (siblings.length > 1) {
          const idx = siblings.indexOf(cur) + 1;
          part += `:nth-of-type(${idx})`;
        }
      }
      parts.unshift(part);
      cur = parent;
    }
    return parts.length ? parts.join(' > ') : el.tagName.toLowerCase();
  }

  function isUniqueSelector(sel) {
    try {
      const matches = document.querySelectorAll(sel);
      return matches.length === 1;
    } catch (_) {
      return false;
    }
  }

  function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/(["\\\]])/g, '\\$1');
  }

  /** 寻找最近的 <label> 文本或 aria-label。 */
  function findLabel(el) {
    // 1. label[for=id]
    if (el.id) {
      const lb = document.querySelector(`label[for="${cssEscape(el.id)}"]`);
      if (lb) return lb.innerText.trim();
    }
    // 2. 包裹的 <label>
    let p = el.parentElement;
    while (p) {
      if (p.tagName === 'LABEL') return p.innerText.trim();
      p = p.parentElement;
    }
    // 3. 前一个兄弟 / 父容器的文字
    let prev = el.previousElementSibling;
    if (prev && prev.innerText && prev.innerText.length < 60) {
      return prev.innerText.trim();
    }
    // 4. 父容器的直接文本
    if (el.parentElement) {
      const clone = el.parentElement.cloneNode(true);
      clone.querySelectorAll('input,textarea,select,button').forEach(n => n.remove());
      const txt = (clone.innerText || '').trim();
      if (txt && txt.length < 60) return txt;
    }
    return '';
  }

  function isVisible(el) {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return false;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false;
    }
    return true;
  }

  function detectRepeatable(el) {
    // 简单启发：父元素 class 中含 repeat/list/items/list-wrap，或父元素有"添加"按钮
    let p = el.parentElement;
    for (let i = 0; i < 4 && p; i++, p = p.parentElement) {
      if (!p.className || typeof p.className !== 'string') continue;
      const cls = p.className.toLowerCase();
      if (/(repeat|list|items|group)/.test(cls)) return true;
      // 找兄弟"添加"按钮
      const addBtn = p.querySelector('button, a, span');
      if (addBtn && /添加|新增|add|plus/i.test(addBtn.innerText || '')) return true;
    }
    return false;
  }

  function getOptions(el) {
    if (el.tagName === 'SELECT') {
      return Array.from(el.options).map(o => (o.value || o.textContent || '').trim()).filter(Boolean);
    }
    return [];
  }

  /**
   * 提取页面中所有"可填"字段。
   * 返回：[{ selector, tag, input_type, name, id, placeholder, label_text, ... }]
   */
  function extractFormFields() {
    const out = [];
    const seen = new Set();
    const sels = ['input', 'textarea', 'select'];
    sels.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        if (!isVisible(el)) return;
        const type = (el.getAttribute('type') || '').toLowerCase();
        if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) return;
        if (el.disabled) return;

        let tag;
        if (type === 'file') tag = 'file';
        else if (el.tagName === 'TEXTAREA') tag = 'textarea';
        else if (el.tagName === 'SELECT') tag = 'select';
        else tag = 'input';

        const selector = buildSelector(el);
        if (seen.has(selector)) return;
        seen.add(selector);

        out.push({
          selector,
          tag,
          input_type: type || null,
          name: el.getAttribute('name') || null,
          id: el.id || null,
          placeholder: el.getAttribute('placeholder') || null,
          label_text: findLabel(el) || null,
          aria_label: el.getAttribute('aria-label') || null,
          required: el.hasAttribute('required'),
          options: getOptions(el),
          in_repeatable_section: detectRepeatable(el),
          section_hint: '',
        });
      });
    });

    // 收集"添加"按钮（用于动态列表）
    const addButtons = [];
    document.querySelectorAll('button, a, span, div[role="button"]').forEach(el => {
      const t = (el.innerText || '').trim();
      if (t && t.length < 30 && /(添加|新增|add|plus|∨)/i.test(t)) {
        const sel = buildSelector(el);
        if (sel && !seen.has(sel)) {
          addButtons.push({ selector: sel, text: t });
        }
      }
    });

    return { fields: out, add_buttons: addButtons };
  }

  // 暴露 API
  window.__RAF_extract = extractFormFields;
})();
