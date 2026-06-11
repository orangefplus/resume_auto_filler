"""端到端 API 测试：使用真实模板调用 /api/fill。"""
import json
import sys
import time
import urllib.request

# 读取真实模板
with open(r'c:\Users\wangxin\Documents\trae_projects\Rag_heima\resume_auto_filler\user_data\profile_template.md', encoding='utf-8') as f:
    template = f.read()

req_body = {
    'page_url': 'https://campus.10g1aks.com.cn/job/apply?id=518',
    'page_title': 'agent算法实习生',
    'fields': [
        {'selector': '#name', 'tag': 'input', 'input_type': 'text', 'name': 'username', 'id': 'name', 'label_text': '姓名', 'required': True, 'options': [], 'in_repeatable_section': False, 'section_hint': ''},
        {'selector': '#email', 'tag': 'input', 'input_type': 'email', 'name': 'email', 'id': 'email', 'label_text': '电子邮箱', 'required': True, 'options': [], 'in_repeatable_section': False, 'section_hint': ''},
        {'selector': '#phone', 'tag': 'input', 'input_type': 'tel', 'name': 'phone', 'id': 'phone', 'label_text': '联系电话', 'required': True, 'options': [], 'in_repeatable_section': False, 'section_hint': ''},
        {'selector': 'select#gender', 'tag': 'select', 'name': 'gender', 'id': 'gender', 'label_text': '性别', 'required': True, 'options': ['男','女'], 'in_repeatable_section': False, 'section_hint': ''},
        {'selector': 'input[type=file][name=resume]', 'tag': 'file', 'input_type': 'file', 'name': 'resume', 'label_text': '简历附件', 'required': True, 'options': [], 'in_repeatable_section': False, 'section_hint': ''},
        {'selector': 'input[type=file][name=avatar]', 'tag': 'file', 'input_type': 'file', 'name': 'avatar', 'label_text': '个人照片', 'required': False, 'options': [], 'in_repeatable_section': False, 'section_hint': ''},
        {'selector': 'textarea#self', 'tag': 'textarea', 'name': 'self', 'id': 'self', 'label_text': '自我评价', 'required': False, 'options': [], 'in_repeatable_section': False, 'section_hint': ''},
        {'selector': 'input[name=city]', 'tag': 'input', 'input_type': 'text', 'name': 'city', 'label_text': '期望工作城市', 'required': False, 'options': [], 'in_repeatable_section': False, 'section_hint': ''},
        {'selector': 'textarea#skills', 'tag': 'textarea', 'name': 'skills', 'id': 'skills', 'label_text': '专业技能', 'required': False, 'options': [], 'in_repeatable_section': False, 'section_hint': ''},
    ],
    'user_markdown': template,
    'file_names': ['张三_简历.pdf', 'photo.jpg'],
}

data = json.dumps(req_body).encode('utf-8')
url = 'http://127.0.0.1:8770/api/fill'
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

t0 = time.time()
with urllib.request.urlopen(req, timeout=120) as r:
    result = json.loads(r.read().decode('utf-8'))
elapsed = time.time() - t0

print('=' * 60)
print('  /api/fill 端到端测试')
print('=' * 60)
print(f'  success       : {result["success"]}')
print(f'  elapsed       : {elapsed:.2f}s')
print(f'  error         : {result.get("error")}')
plan = result['plan']
print(f'  matched_count : {plan["matched_count"]}')
print(f'  actions       : {len(plan["actions"])}')
print(f'  unmatched     : {plan["unmatched_fields"]}')
print(f'  notes         : {plan["notes"]}')
print()
print('  【动作清单】')
for i, a in enumerate(plan['actions'], 1):
    if a['action'] == 'type':
        detail = a.get('value', '')
    elif a['action'] == 'set_file':
        detail = f"file[{a.get('file_index')}]"
    else:
        detail = ''
    print(f'    {i}. [{a["action"]:12s}] {a["selector"]:35s} -> {detail}')
print()
print('  【Profile 摘要】')
for line in (result.get('profile_summary') or '').split('\n'):
    print(f'    {line}')
print('=' * 60)
