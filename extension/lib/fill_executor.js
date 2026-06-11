// 填写执行器：把后端返回的 FillPlan 在当前页面上执行。
// 暴露：window.__RAF_execute(plan, files) -> Promise<results>
(function () {
  'use strict';

  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  function el(sel) {
    try {
      return document.querySelector(sel);
    } catch (e) {
      // 某些 selector 可能在不规范页面里抛错
      return null;
    }
  }

  function all(sel) {
    try { return Array.from(document.querySelectorAll(sel)); }
    catch (e) { return []; }
  }

  /**
   * 模拟"人输入"：分多个字符触发，确保 Vue/React 受控组件能监听到。
   * 用 nativeInputValueSetter 绕过 React 的 value 跟踪。
   */
  async function typeText(input, text) {
    if (!input) return false;
    input.focus();

    const isTextarea = input.tagName === 'TEXTAREA';
    const proto = isTextarea
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;

    // 先清空
    setter.call(input, '');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await sleep(50);

    // 整段写入（分块以触发 input 事件）
    const chunks = chunkString(text, 20);
    for (const chunk of chunks) {
      setter.call(input, (input.value || '') + chunk);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      await sleep(20);
    }
    input.dispatchEvent(new Event('blur', { bubbles: true }));
    return true;
  }

  function chunkString(s, size) {
    const out = [];
    for (let i = 0; i < s.length; i += size) out.push(s.slice(i, i + size));
    return out;
  }

  async function setSelect(sel, value) {
    if (!sel) return false;
    // 1. 找精确匹配 option
    let option = Array.from(sel.options).find(o =>
      (o.value || '').toLowerCase() === value.toLowerCase() ||
      (o.textContent || '').trim().toLowerCase() === value.toLowerCase()
    );
    // 2. 子串匹配
    if (!option) {
      option = Array.from(sel.options).find(o =>
        (o.textContent || '').toLowerCase().includes(value.toLowerCase()) ||
        (o.value || '').toLowerCase().includes(value.toLowerCase())
      );
    }
    if (!option) {
      // 3. 模糊拼音/首字匹配留给业务，这里只打 warning
      console.warn('[RAF] setSelect 未找到 option:', value, '现有 options:',
        Array.from(sel.options).map(o => o.textContent));
      return false;
    }
    sel.value = option.value;
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    sel.dispatchEvent(new Event('input', { bubbles: true }));
    sel.dispatchEvent(new Event('blur', { bubbles: true }));
    return true;
  }

  /**
   * 设置文件：用 DataTransfer 注入 File 对象。
   * 关键：File 对象必须由 sidepanel 通过消息传过来（content script 无法读取本地文件）。
   */
  function setFileInput(input, file) {
    if (!input || !file) return false;
    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    } catch (e) {
      console.error('[RAF] setFile 失败:', e);
      return false;
    }
  }

  async function clickButton(sel) {
    const btn = el(sel);
    if (!btn) return false;
    btn.scrollIntoView({ block: 'center' });
    btn.click();
    return true;
  }

  /**
   * 执行 FillPlan。
   * @param {Object} plan  { actions: [...] }
   * @param {File[]} files 用户在侧栏选的文件
   */
  async function executeFillPlan(plan, files) {
    const results = [];
    for (const action of (plan && plan.actions) || []) {
      await sleep(action.delay_ms || 150);
      let ok = false;
      let detail = '';
      try {
        switch (action.action) {
          case 'type': {
            const e = el(action.selector);
            ok = await typeText(e, action.value || '');
            detail = ok ? `已填 "${truncate(action.value, 30)}"` : '未找到输入框';
            break;
          }
          case 'set_select': {
            const e = el(action.selector);
            ok = await setSelect(e, action.value || '');
            detail = ok ? `已选 "${action.value}"` : '未找到匹配的 option';
            break;
          }
          case 'set_file': {
            const e = el(action.selector);
            const idx = action.file_index || 0;
            const f = files && files[idx];
            if (!f) {
              ok = false;
              detail = `没有第 ${idx + 1} 个文件`;
            } else {
              ok = setFileInput(e, f);
              detail = ok ? `已上传文件 ${f.name}` : '注入 File 失败';
            }
            break;
          }
          case 'click': {
            ok = await clickButton(action.selector);
            detail = ok ? '已点击' : '未找到按钮';
            break;
          }
          case 'check':
          case 'uncheck': {
            const e = el(action.selector);
            if (e && e.type === 'checkbox') {
              const want = action.action === 'check';
              if (e.checked !== want) e.click();
              ok = true;
              detail = action.action === 'check' ? '已勾选' : '已取消勾选';
            } else {
              detail = '未找到 checkbox';
            }
            break;
          }
          case 'clear': {
            const e = el(action.selector);
            if (e) {
              e.value = '';
              e.dispatchEvent(new Event('input', { bubbles: true }));
              ok = true;
              detail = '已清空';
            }
            break;
          }
          default:
            detail = `未知动作: ${action.action}`;
        }
      } catch (e) {
        ok = false;
        detail = `异常: ${e && e.message ? e.message : e}`;
      }
      results.push({
        selector: action.selector,
        action: action.action,
        ok,
        detail,
      });
    }
    return results;
  }

  function truncate(s, n) {
    if (!s) return '';
    return s.length > n ? s.slice(0, n) + '...' : s;
  }

  window.__RAF_execute = executeFillPlan;
})();
