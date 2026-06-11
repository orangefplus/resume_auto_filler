// Side Panel 逻辑
(function () {
  'use strict';

  // ------- 元素 -------
  const $ = (id) => document.getElementById(id);
  const statusDot = $('statusDot');
  const statusText = $('statusText');
  const pageUrl = $('pageUrl');
  const mdInput = $('mdInput');
  const fileInput = $('fileInput');
  const fileListEl = $('fileList');
  const fillBtn = $('fillBtn');
  const extractBtn = $('extractBtn');
  const logBox = $('logBox');
  const loadTemplateBtn = $('loadTemplate');
  const settingsBtn = $('settingsBtn');
  const settingsPanel = $('settingsPanel');
  const backendInput = $('backendInput');
  const saveBackendBtn = $('saveBackend');
  const cancelSettingsBtn = $('cancelSettings');
  const profileCard = $('profileCard');
  const profileSummary = $('profileSummary');

  // 状态
  let selectedFiles = [];   // File[]
  let lastFields = [];      // 提取出的 fields
  let lastAddButtons = [];  // 添加按钮

  // ------- 工具 -------
  function log(level, msg) {
    const div = document.createElement('div');
    div.className = 'log-line';
    const tag = document.createElement('span');
    tag.className = `tag ${level}`;
    tag.textContent = level === 'ok' ? '✓' : level === 'err' ? '✗' : level === 'warn' ? '!' : '·';
    const m = document.createElement('span');
    m.className = 'msg';
    m.textContent = msg;
    div.appendChild(tag);
    div.appendChild(m);
    if (logBox.querySelector('.log-empty')) logBox.innerHTML = '';
    logBox.appendChild(div);
    logBox.scrollTop = logBox.scrollHeight;
  }

  function setStatus(state, text) {
    statusDot.className = 'status-dot ' + (state || '');
    statusText.textContent = text || '';
  }

  function send(type, payload) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type, ...payload }, (resp) => resolve(resp));
    });
  }

  function getCurrentTab() {
    return new Promise((resolve) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        resolve(tabs && tabs[0]);
      });
    });
  }

  // ------- 初始化 -------
  async function init() {
    setStatus('warn', '检测中…');
    const tab = await getCurrentTab();
    if (tab) pageUrl.textContent = tab.url || '-';

    // 健康检查
    const h = await send('RAF_BACKEND_HEALTH');
    if (h && h.ok && h.data && h.data.status === 'ok') {
      setStatus('ok', `已连接 · ${h.data.model}`);
    } else {
      setStatus('err', '后端未启动');
    }
  }

  // ------- 文件 -------
  fileInput.addEventListener('change', () => {
    selectedFiles = Array.from(fileInput.files || []);
    fileListEl.innerHTML = '';
    selectedFiles.forEach(f => {
      const tag = document.createElement('span');
      tag.className = 'file-tag';
      tag.textContent = `${f.name} (${formatSize(f.size)})`;
      fileListEl.appendChild(tag);
    });
  });

  function formatSize(b) {
    if (b < 1024) return b + 'B';
    if (b < 1024 * 1024) return (b / 1024).toFixed(1) + 'KB';
    return (b / 1024 / 1024).toFixed(1) + 'MB';
  }

  // ------- 模板 -------
  loadTemplateBtn.addEventListener('click', () => {
    mdInput.value = TEMPLATE_MD.trim();
    log('info', '已加载示例模板');
  });

  // ------- 设置 -------
  settingsBtn.addEventListener('click', async () => {
    const r = await send('RAF_GET_BACKEND');
    backendInput.value = (r && r.backend) || 'http://127.0.0.1:8765';
    settingsPanel.hidden = false;
  });
  cancelSettingsBtn.addEventListener('click', () => { settingsPanel.hidden = true; });
  saveBackendBtn.addEventListener('click', async () => {
    const v = backendInput.value.trim();
    await send('RAF_SET_BACKEND', { backend: v });
    settingsPanel.hidden = true;
    log('ok', `后端地址已保存：${v}`);
    init();
  });

  // ------- 仅提取字段 -------
  extractBtn.addEventListener('click', async () => {
    fillBtn.disabled = true;
    setStatus('warn', '提取中…');
    log('info', '正在提取当前页面表单字段…');
    const tab = await getCurrentTab();
    const r = await send('RAF_BACKEND_EXTRACT', { tabId: tab.id });
    if (r && r.ok) {
      lastFields = r.data.fields || [];
      lastAddButtons = r.data.add_buttons || [];
      log('ok', `已提取 ${lastFields.length} 个字段${lastAddButtons.length ? `，${lastAddButtons.length} 个"添加"按钮` : ''}`);
      log('info', '字段列表：');
      lastFields.slice(0, 12).forEach((f, i) => {
        log('info', `  #${i + 1} [${f.tag}${f.input_type ? ':' + f.input_type : ''}] ${f.label_text || f.placeholder || f.name || f.id || ''}`);
      });
      if (lastFields.length > 12) log('info', `  ... 还有 ${lastFields.length - 12} 个`);
      setStatus('ok', '已提取字段');
    } else {
      log('err', `提取失败：${r && r.error}`);
      setStatus('err', '提取失败');
    }
    fillBtn.disabled = false;
  });

  // ------- 智能填写 -------
  fillBtn.addEventListener('click', async () => {
    const md = mdInput.value.trim();
    if (!md) {
      log('err', '请先粘贴或加载简历内容');
      mdInput.focus();
      return;
    }

    fillBtn.disabled = true;
    setStatus('warn', '处理中…');
    log('info', '① 提取当前页面表单字段…');

    const tab = await getCurrentTab();
    const ex = await send('RAF_BACKEND_EXTRACT', { tabId: tab.id });
    if (!ex || !ex.ok) {
      log('err', `提取字段失败：${ex && ex.error}`);
      setStatus('err', '提取失败');
      fillBtn.disabled = false;
      return;
    }
    const fields = ex.data.fields || [];
    lastFields = fields;
    log('ok', `已提取 ${fields.length} 个字段`);

    if (fields.length === 0) {
      log('warn', '当前页面没有检测到表单字段');
      fillBtn.disabled = false;
      return;
    }

    log('info', '② 调用后端 Qwen Agent 生成填写计划…');
    const fileNames = selectedFiles.map(f => f.name);
    const fillResp = await send('RAF_BACKEND_FILL', {
      payload: {
        page_url: tab.url,
        page_title: tab.title,
        fields: fields,
        user_markdown: md,
        file_names: fileNames,
      },
    });

    if (!fillResp || !fillResp.ok) {
      log('err', `后端失败：${fillResp && fillResp.error}`);
      setStatus('err', '后端失败');
      fillBtn.disabled = false;
      return;
    }

    const data = fillResp.data;
    if (!data.success) {
      log('err', `后端处理失败：${data.error || '未知'}`);
      fillBtn.disabled = false;
      return;
    }

    const plan = data.plan || {};
    log('ok', `解析完成：${data.profile_summary ? data.profile_summary.split('\n')[0] : ''}`);
    log('info', `③ FillPlan：${plan.actions.length} 个动作（${plan.notes || ''}）`);

    if (data.profile_summary) {
      profileCard.hidden = false;
      profileSummary.textContent = data.profile_summary;
    }

    log('info', '④ 在页面上执行填写…');
    const er = await send('RAF_BACKEND_EXECUTE', {
      tabId: tab.id,
      plan: plan,
      files: selectedFiles,
    });

    if (!er || !er.ok) {
      log('err', `执行失败：${er && er.error}`);
      setStatus('err', '执行失败');
      fillBtn.disabled = false;
      return;
    }

    let succ = 0, fail = 0;
    (er.results || []).forEach((r, i) => {
      if (r.ok) {
        log('ok', `${i + 1}. ${r.detail}`);
        succ++;
      } else {
        log('err', `${i + 1}. ${r.detail} [${truncate(r.selector, 30)}]`);
        fail++;
      }
    });
    log('ok', `完成：成功 ${succ}，失败 ${fail}`);
    if (plan.unmatched_fields && plan.unmatched_fields.length) {
      log('warn', `未匹配字段：${plan.unmatched_fields.slice(0, 6).join('、')}${plan.unmatched_fields.length > 6 ? '…' : ''}`);
    }
    setStatus(fail === 0 ? 'ok' : 'warn', `成功 ${succ} / 失败 ${fail}`);

    fillBtn.disabled = false;
  });

  function truncate(s, n) {
    if (!s) return '';
    return s.length > n ? s.slice(0, n) + '…' : s;
  }

  // ------- 内置模板 -------
  const TEMPLATE_MD = `
## 基本信息
- 姓名：张三
- 性别：男
- 出生：1999-01
- 手机：13800000000
- 邮箱：zhangsan@example.com
- 现居：北京

## 教育经历
### 北京大学 - 计算机科学与技术 - 本科
- 时间：2020-09 至 2024-06
- 主修课程：数据结构、操作系统、计算机网络、机器学习
- GPA：3.8/4.0

### 清华大学 - 人工智能 - 硕士
- 时间：2024-09 至 2026-06
- 研究方向：大语言模型、智能体

## 实习经历
### 阿里巴巴 - 算法实习生
- 时间：2023-07 至 2023-09
- 描述：负责推荐系统中 CTR 模型的特征工程与训练，引入 DIN 网络使 AUC 提升 3.2%。

## 项目经历
### 智能客服问答系统
- 时间：2023-03 至 2023-06
- 角色：负责人
- 描述：基于 RAG + Qwen 7B 构建校园知识库问答机器人，使用 LangChain 编排，ChromaDB 存储向量。

## 专业技能
- Python、PyTorch、SQL、LangChain
- 熟悉 Transformer / BERT / LLM 微调 (LoRA / RLHF)
- 熟悉 Docker / Linux / Git

## 语言能力
- 英语 CET-6 (560)
- 日语 N2

## 获奖情况
- 2022 全国大学生数学建模竞赛 国家一等奖
- 2021 蓝桥杯 Python 组 省一等奖

## 自我评价
热爱 AI 技术，熟练使用 PyTorch / Transformers。具备良好的工程能力与团队协作精神。
`.trim();

  // 启动
  init();
})();
