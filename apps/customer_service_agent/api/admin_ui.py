"""后台管理页面路由：返回 HTML 单页应用。"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/admin", tags=["admin-ui"])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_page() -> str:
    return ADMIN_HTML


ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>客服知识库管理系统</title>
<style>
:root {
  --primary: #635bff;
  --primary-dark: #5a4edb;
  --bg: #f6f9fc;
  --card: #ffffff;
  --border: #e3e8ee;
  --text: #1a1f36;
  --text-muted: #697386;
  --danger: #df1b41;
  --success: #1a8450;
  --radius: 8px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans CJK SC', sans-serif; background: var(--bg); color: var(--text); }
.sidebar { position: fixed; left: 0; top: 0; width: 220px; height: 100vh; background: var(--card); border-right: 1px solid var(--border); padding: 20px 0; display: flex; flex-direction: column; }
.sidebar-logo { padding: 0 20px 20px; font-size: 16px; font-weight: 700; color: var(--primary); border-bottom: 1px solid var(--border); }
.nav-item { padding: 12px 20px; cursor: pointer; font-size: 14px; color: var(--text-muted); transition: all .15s; display: flex; align-items: center; gap: 8px; }
.nav-item:hover { background: var(--bg); color: var(--text); }
.nav-item.active { color: var(--primary); background: #f0efff; border-right: 3px solid var(--primary); font-weight: 600; }
.main { margin-left: 220px; padding: 24px 32px; min-height: 100vh; }
.page { display: none; }
.page.active { display: block; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; }
.stat-label { font-size: 13px; color: var(--text-muted); margin-bottom: 8px; }
.stat-value { font-size: 28px; font-weight: 700; }
.stat-card.primary .stat-value { color: var(--primary); }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border: none; border-radius: var(--radius); font-size: 14px; cursor: pointer; transition: all .15s; font-weight: 500; }
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-dark); }
.btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text); }
.btn-outline:hover { background: var(--bg); }
.btn-danger { background: transparent; border: 1px solid var(--danger); color: var(--danger); padding: 4px 10px; font-size: 13px; }
.btn-danger:hover { background: var(--danger); color: #fff; }
.btn-sm { padding: 4px 10px; font-size: 13px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 16px; overflow: hidden; }
.card-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.card-body { padding: 20px; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 12px 16px; font-size: 13px; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border); background: var(--bg); }
td { padding: 12px 16px; font-size: 14px; border-bottom: 1px solid var(--border); }
tr:hover { background: #fafbfd; }
.tag { display: inline-block; padding: 2px 8px; background: #f0efff; color: var(--primary); border-radius: 12px; font-size: 12px; margin: 2px; }
.form-group { margin-bottom: 16px; }
.form-label { display: block; font-size: 14px; font-weight: 500; margin-bottom: 6px; }
.form-input, .form-textarea, .form-select { width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 14px; font-family: inherit; }
.form-input:focus, .form-textarea:focus, .form-select:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(99,91,255,.12); }
.form-textarea { min-height: 100px; resize: vertical; }
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,.4); z-index: 1000; justify-content: center; align-items: center; }
.modal-overlay.show { display: flex; }
.modal { background: var(--card); border-radius: var(--radius); width: 560px; max-height: 80vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,.15); }
.modal-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.modal-title { font-size: 16px; font-weight: 700; }
.modal-close { cursor: pointer; font-size: 20px; color: var(--text-muted); border: none; background: none; }
.modal-body { padding: 20px; }
.modal-footer { padding: 16px 20px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 8px; }
.toast { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: var(--radius); color: #fff; font-size: 14px; z-index: 2000; animation: slideIn .3s; }
.toast-success { background: var(--success); }
.toast-error { background: var(--danger); }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.filter-bar select, .filter-bar input { padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 14px; }
.filter-bar input { flex: 1; min-width: 200px; }
.empty { text-align: center; padding: 40px; color: var(--text-muted); }
.message-bubble { padding: 10px 14px; border-radius: 12px; margin-bottom: 8px; max-width: 70%; }
.message-user { background: #f0efff; margin-left: auto; }
.message-assistant { background: #f6f9fc; border: 1px solid var(--border); }
.message-role { font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
.pagination { display: flex; justify-content: center; gap: 8px; margin-top: 16px; }
.pager-btn { padding: 6px 12px; border: 1px solid var(--border); border-radius: var(--radius); cursor: pointer; font-size: 14px; background: var(--card); }
.pager-btn:hover { background: var(--bg); }
.pager-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.pager-btn:disabled { opacity: .4; cursor: not-allowed; }
</style>
</head>
<body>

<div class="sidebar">
  <div class="sidebar-logo">AI 客服管理后台</div>
  <div class="nav-item active" onclick="switchPage('dashboard', event)">📊 仪表盘</div>
  <div class="nav-item" onclick="switchPage('knowledge', event)">📚 知识库管理</div>
  <div class="nav-item" onclick="switchPage('sessions', event)">💬 会话记录</div>
  <div class="nav-item" onclick="switchPage('playground', event)">🧪 测试问答</div>
  <div class="nav-item" onclick="switchPage('batch-test', event)">📋 批量测试</div>
</div>

<div class="main">

<!-- ===== 仪表盘 ===== -->
<div id="page-dashboard" class="page active">
  <div class="page-header"><div class="page-title">仪表盘</div></div>
  <div class="stats-grid">
    <div class="stat-card primary"><div class="stat-label">知识库总数</div><div class="stat-value" id="stat-kb-total">-</div></div>
    <div class="stat-card"><div class="stat-label">FAQ 常见问题</div><div class="stat-value" id="stat-kb-faq">-</div></div>
    <div class="stat-card"><div class="stat-label">商品知识</div><div class="stat-value" id="stat-kb-product">-</div></div>
    <div class="stat-card"><div class="stat-label">售后规则</div><div class="stat-value" id="stat-kb-policy">-</div></div>
  </div>
  <div class="stats-grid">
    <div class="stat-card"><div class="stat-label">会话记录</div><div class="stat-value" id="stat-sessions">-</div></div>
    <div class="stat-card"><div class="stat-label">消息总数</div><div class="stat-value" id="stat-messages">-</div></div>
  </div>
</div>

<!-- ===== 知识库管理 ===== -->
<div id="page-knowledge" class="page">
  <div class="page-header">
    <div class="page-title">知识库管理</div>
    <div>
      <button class="btn btn-outline" onclick="openBatchModal()">📥 批量导入</button>
      <button class="btn btn-primary" onclick="openKnowledgeModal()">➕ 新增知识点</button>
    </div>
  </div>
  <div class="filter-bar">
    <select id="kb-collection" onchange="loadKnowledge()">
      <option value="kb_faq">FAQ 常见问题</option>
      <option value="kb_product">商品知识</option>
      <option value="kb_policy">售后规则</option>
    </select>
    <input type="text" id="kb-search" placeholder="搜索问题或答案..." onkeyup="if(event.key==='Enter')loadKnowledge()">
    <button class="btn btn-outline btn-sm" onclick="loadKnowledge()">🔍 搜索</button>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>问题</th><th>答案</th><th>标签</th><th style="width:120px">操作</th></tr></thead>
      <tbody id="kb-table-body"></tbody>
    </table>
  </div>
  <div class="pagination" id="kb-pagination"></div>
</div>

<!-- ===== 会话记录 ===== -->
<div id="page-sessions" class="page">
  <div class="page-header">
    <div class="page-title">会话记录</div>
    <button class="btn btn-primary" onclick="openSessionModal()">➕ 录入会话</button>
  </div>
  <div class="filter-bar">
    <select id="session-platform" onchange="loadSessions()">
      <option value="">全部平台</option>
      <option value="doudian">抖店</option>
      <option value="taobao">淘宝</option>
    </select>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>买家ID</th><th>平台</th><th>店铺ID</th><th>消息数</th><th>创建时间</th><th style="width:150px">操作</th></tr></thead>
      <tbody id="session-table-body"></tbody>
    </table>
  </div>
  <div class="pagination" id="session-pagination"></div>
</div>

<!-- ===== 测试问答页面 ===== -->
<div id="page-playground" class="page">
  <div class="page-header"><div class="page-title">测试问答</div></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
    <!-- 左侧：输入区 -->
    <div class="card">
      <div class="card-header"><div style="font-weight:600">输入问题</div></div>
      <div class="card-body">
        <div class="form-group">
          <label class="form-label">顾客问题</label>
          <textarea class="form-textarea" id="pg-question" style="min-height:120px" placeholder="输入要测试的客服问题，如：发货时间是多久？"></textarea>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <button class="btn btn-primary" id="pg-submit-btn" onclick="askQuestion()">🚀 发送提问</button>
          <button class="btn btn-outline" onclick="clearPlayground()">清空</button>
          <span id="pg-status" style="font-size:13px;color:var(--text-muted)"></span>
        </div>
        <div style="margin-top:16px;border-top:1px solid var(--border);padding-top:16px;">
          <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">💡 快捷问题（点击直接测试）</div>
          <div id="pg-quick-questions" style="display:flex;flex-wrap:wrap;gap:8px;"></div>
        </div>
      </div>
    </div>
    <!-- 右侧：回答区 -->
    <div class="card">
      <div class="card-header">
        <div style="font-weight:600">AI 回答</div>
        <span id="pg-match-badge" style="display:none"></span>
      </div>
      <div class="card-body">
        <div id="pg-answer-area" style="min-height:200px;">
          <div class="empty">在左侧输入问题后点击"发送提问"查看回答</div>
        </div>
      </div>
    </div>
  </div>
  <!-- 匹配来源 -->
  <div class="card" style="margin-top:20px;">
    <div class="card-header"><div style="font-weight:600">匹配知识来源</div></div>
    <div class="card-body">
      <div id="pg-sources-area">
        <div class="empty">提问后将展示命中的知识库片段</div>
      </div>
    </div>
  </div>
  <!-- 历史测试记录 -->
  <div class="card" style="margin-top:20px;">
    <div class="card-header">
      <div style="font-weight:600">本次测试记录</div>
      <button class="btn btn-outline btn-sm" onclick="clearHistory()">清空记录</button>
    </div>
    <div class="card-body" style="padding:0">
      <div id="pg-history-area" style="max-height:300px;overflow-y:auto">
        <div class="empty" style="padding:20px">暂无测试记录</div>
      </div>
    </div>
  </div>
</div>

<!-- ===== 批量测试页面 ===== -->
<div id="page-batch-test" class="page">
  <div class="page-header"><div class="page-title">批量测试</div></div>

  <!-- 操作区 -->
  <div class="card" style="margin-bottom:20px;">
    <div class="card-body">
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
        <input type="file" id="bt-file-input" accept=".xlsx,.xls" style="display:none" onchange="uploadExcel()">
        <button class="btn btn-primary" onclick="document.getElementById('bt-file-input').click()">📤 上传 Excel</button>
        <button class="btn btn-outline" onclick="downloadTemplate()">📥 下载模板</button>
        <span style="font-size:13px;color:var(--text-muted)">支持列：问题 / 期望答案 / 分类 / 备注</span>
      </div>
    </div>
  </div>

  <!-- 任务列表 -->
  <div class="card">
    <div class="card-header"><div style="font-weight:600">测试任务</div></div>
    <div class="card-body" style="padding:0">
      <table>
        <thead><tr><th>文件名</th><th>进度</th><th>状态</th><th>已审核</th><th>准确率</th><th>创建时间</th><th style="width:200px">操作</th></tr></thead>
        <tbody id="bt-task-list">
          <tr><td colspan="7" class="empty">暂无测试任务，请上传 Excel</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

</div><!-- /main -->

<!-- ===== 知识点编辑弹窗 ===== -->
<div class="modal-overlay" id="knowledge-modal">
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title" id="knowledge-modal-title">新增知识点</div>
      <button class="modal-close" onclick="closeModal('knowledge-modal')">&times;</button>
    </div>
    <div class="modal-body">
      <input type="hidden" id="kb-edit-id">
      <div class="form-group">
        <label class="form-label">知识集合</label>
        <select class="form-select" id="kb-modal-collection">
          <option value="kb_faq">FAQ 常见问题</option>
          <option value="kb_product">商品知识</option>
          <option value="kb_policy">售后规则</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">录入模式</label>
        <div style="display:flex;gap:12px;align-items:center">
          <label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:14px">
            <input type="radio" name="kb-mode" value="qa" checked onchange="switchKbMode('qa')"> QA 问答模式
          </label>
          <label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:14px">
            <input type="radio" name="kb-mode" value="knowledge" onchange="switchKbMode('knowledge')"> 纯知识模式
          </label>
        </div>
      </div>
      <!-- QA 模式字段 -->
      <div class="form-group" id="kb-qa-fields">
        <label class="form-label">问题</label>
        <input type="text" class="form-input" id="kb-modal-question" placeholder="如：发货时间是多久？">
        <label class="form-label" style="margin-top:12px">答案</label>
        <textarea class="form-textarea" id="kb-modal-answer" placeholder="如：现货商品下单后24小时内发货..."></textarea>
      </div>
      <!-- 纯知识模式字段 -->
      <div class="form-group" id="kb-knowledge-fields" style="display:none">
        <label class="form-label">标题</label>
        <input type="text" class="form-input" id="kb-modal-title" placeholder="如：优惠券使用规则">
        <label class="form-label" style="margin-top:12px">内容</label>
        <textarea class="form-textarea" id="kb-modal-content" placeholder="如：优惠券无法使用的5种原因...（支持多行）" style="min-height:120px"></textarea>
      </div>
      <div class="form-group">
        <label class="form-label">标签（逗号分隔）</label>
        <input type="text" class="form-input" id="kb-modal-tags" placeholder="如：发货,时效">
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal('knowledge-modal')">取消</button>
      <button class="btn btn-primary" onclick="saveKnowledge()">保存</button>
    </div>
  </div>
</div>

<!-- ===== 批量导入弹窗 ===== -->
<div class="modal-overlay" id="batch-modal">
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title">批量导入知识点</div>
      <button class="modal-close" onclick="closeModal('batch-modal')">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label class="form-label">目标集合</label>
        <select class="form-select" id="batch-collection">
          <option value="kb_faq">FAQ 常见问题</option>
          <option value="kb_product">商品知识</option>
          <option value="kb_policy">售后规则</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">JSONL 数据（每行一个 JSON 对象）</label>
        <textarea class="form-textarea" id="batch-data" style="min-height:200px" placeholder='{"question":"问题1","answer":"答案1","tags":["标签"]}&#10;{"question":"问题2","answer":"答案2"}'></textarea>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal('batch-modal')">取消</button>
      <button class="btn btn-primary" onclick="batchIngest()">导入</button>
    </div>
  </div>
</div>

<!-- ===== 会话录入弹窗 ===== -->
<div class="modal-overlay" id="session-modal">
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title">录入会话记录</div>
      <button class="modal-close" onclick="closeModal('session-modal')">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label class="form-label">买家ID</label>
        <input type="text" class="form-input" id="sess-buyer-id" placeholder="买家标识">
      </div>
      <div class="form-group">
        <label class="form-label">平台</label>
        <select class="form-select" id="sess-platform">
          <option value="doudian">抖店</option>
          <option value="taobao">淘宝</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">店铺ID</label>
        <input type="text" class="form-input" id="sess-shop-id" placeholder="店铺标识（可选）">
      </div>
      <div class="form-group">
        <label class="form-label">对话内容（每行一条，格式：角色|内容）</label>
        <textarea class="form-textarea" id="sess-messages" style="min-height:200px" placeholder="user|这个色号适合黄皮吗？&#10;assistant|这款#12号色非常适合黄皮，能提亮肤色...&#10;user|发什么快递？&#10;assistant|默认发中通快递，也可备注指定。"></textarea>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal('session-modal')">取消</button>
      <button class="btn btn-primary" onclick="saveSession()">保存</button>
    </div>
  </div>
</div>

<!-- ===== 会话详情弹窗 ===== -->
<div class="modal-overlay" id="session-detail-modal">
  <div class="modal" style="width:680px">
    <div class="modal-header">
      <div class="modal-title">会话详情</div>
      <button class="modal-close" onclick="closeModal('session-detail-modal')">&times;</button>
    </div>
    <div class="modal-body" id="session-detail-body"></div>
  </div>
</div>

<!-- ===== 批量测试结果弹窗 ===== -->
<div class="modal-overlay" id="bt-result-modal">
  <div class="modal" style="width:90%;max-width:1100px">
    <div class="modal-header">
      <div class="modal-title">测试结果 — <span id="bt-modal-filename"></span></div>
      <button class="modal-close" onclick="closeModal('bt-result-modal')">&times;</button>
    </div>
    <div class="modal-body">
      <!-- 进度统计 -->
      <div id="bt-progress-bar" style="margin-bottom:16px;"></div>
      <!-- 筛选 -->
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;">
        <span style="font-size:13px;color:var(--text-muted)">审核筛选：</span>
        <button class="btn btn-outline btn-sm bt-filter-btn active" data-filter="" onclick="btSetFilter('')">全部</button>
        <button class="btn btn-outline btn-sm bt-filter-btn" data-filter="pending" onclick="btSetFilter('pending')">待审核</button>
        <button class="btn btn-outline btn-sm bt-filter-btn" data-filter="correct" onclick="btSetFilter('correct')">正确</button>
        <button class="btn btn-outline btn-sm bt-filter-btn" data-filter="incorrect" onclick="btSetFilter('incorrect')">错误</button>
        <span style="flex:1"></span>
        <button class="btn btn-outline btn-sm" onclick="exportResults()">📥 导出结果</button>
      </div>
      <!-- 结果表格 -->
      <div style="max-height:500px;overflow-y:auto">
        <table style="width:100%">
          <thead><tr><th style="width:30px">#</th><th style="width:25%">问题</th><th style="width:25%">AI回答</th><th style="width:20%">期望答案</th><th>命中</th><th style="width:90px">耗时</th><th style="width:120px">审核</th></tr></thead>
          <tbody id="bt-results-body"></tbody>
        </table>
      </div>
      <div class="pagination" id="bt-pagination"></div>
    </div>
  </div>
</div>

<script>
const API = '/admin/api';
let kbOffset = 0, sessOffset = 0;
const PAGE_SIZE = 20;

// ===== 通用 =====
function toast(msg, type='success') {
  const t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}
function closeModal(id) { document.getElementById(id).classList.remove('show'); }
function openModal(id) { document.getElementById(id).classList.add('show'); }
function switchPage(name, evt) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  evt.currentTarget.classList.add('active');
  if (name === 'dashboard') loadStats();
  if (name === 'knowledge') loadKnowledge();
  if (name === 'sessions') loadSessions();
  if (name === 'playground') loadQuickQuestions();
  if (name === 'batch-test') loadBtTasks();
}

// ===== 仪表盘 =====
async function loadStats() {
  try {
    const res = await fetch(API + '/stats');
    const data = await res.json();
    document.getElementById('stat-kb-total').textContent = data.knowledge_total;
    document.getElementById('stat-kb-faq').textContent = data.knowledge_base.kb_faq || 0;
    document.getElementById('stat-kb-product').textContent = data.knowledge_base.kb_product || 0;
    document.getElementById('stat-kb-policy').textContent = data.knowledge_base.kb_policy || 0;
    document.getElementById('stat-sessions').textContent = data.sessions;
    document.getElementById('stat-messages').textContent = data.messages;
  } catch(e) { console.error(e); }
}

// ===== 知识库 =====
async function loadKnowledge() {
  const collection = document.getElementById('kb-collection').value;
  const search = document.getElementById('kb-search').value;
  const res = await fetch(`${API}/knowledge?collection=${collection}&search=${encodeURIComponent(search)}&limit=${PAGE_SIZE}&offset=${kbOffset}`);
  const data = await res.json();
  const tbody = document.getElementById('kb-table-body');
  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">暂无知识点，点击右上角新增</td></tr>';
  } else {
    tbody.innerHTML = data.items.map(item => {
      const isQA = !!item.question;
      const col1 = isQA ? escapeHtml(item.question) : `<span style="color:#888">[知识]</span> ${escapeHtml(item.title || '')}`;
      const col2 = isQA ? escapeHtml(item.answer) : escapeHtml((item.content || '').substring(0, 80) + ((item.content||'').length > 80 ? '...' : ''));
      return `
      <tr>
        <td>${col1}</td>
        <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${col2}</td>
        <td>${(item.tags||[]).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="editKnowledge('${item.id}','${collection}')">编辑</button>
          <button class="btn btn-danger" onclick="deleteKnowledge('${item.id}','${collection}')">删除</button>
        </td>
      </tr>`;
    }).join('');
  }
  renderPagination('kb-pagination', data.total, kbOffset, (newOffset) => { kbOffset = newOffset; loadKnowledge(); });
}
function switchKbMode(mode) {
  const qaFields = document.getElementById('kb-qa-fields');
  const knFields = document.getElementById('kb-knowledge-fields');
  if (mode === 'qa') {
    qaFields.style.display = '';
    knFields.style.display = 'none';
  } else {
    qaFields.style.display = 'none';
    knFields.style.display = '';
  }
}
function openKnowledgeModal() {
  document.getElementById('knowledge-modal-title').textContent = '新增知识点';
  document.getElementById('kb-edit-id').value = '';
  document.getElementById('kb-modal-collection').value = document.getElementById('kb-collection').value;
  document.getElementById('kb-modal-question').value = '';
  document.getElementById('kb-modal-answer').value = '';
  document.getElementById('kb-modal-title').value = '';
  document.getElementById('kb-modal-content').value = '';
  document.getElementById('kb-modal-tags').value = '';
  // 默认 QA 模式
  document.querySelector('input[name="kb-mode"][value="qa"]').checked = true;
  switchKbMode('qa');
  document.getElementById('knowledge-modal').classList.add('show');
}
function editKnowledge(id, collection) {
  // 从表格数据中找到记录
  fetch(`${API}/knowledge?collection=${collection}&limit=200&offset=0`)
    .then(r => r.json())
    .then(data => {
      const item = data.items.find(i => i.id === id);
      if (!item) return;
      document.getElementById('knowledge-modal-title').textContent = '编辑知识点';
      document.getElementById('kb-edit-id').value = id;
      document.getElementById('kb-modal-collection').value = collection;
      // 根据数据自动切换到对应模式
      if (item.question) {
        document.querySelector('input[name="kb-mode"][value="qa"]').checked = true;
        switchKbMode('qa');
        document.getElementById('kb-modal-question').value = item.question;
        document.getElementById('kb-modal-answer').value = item.answer;
        document.getElementById('kb-modal-title').value = '';
        document.getElementById('kb-modal-content').value = '';
      } else {
        document.querySelector('input[name="kb-mode"][value="knowledge"]').checked = true;
        switchKbMode('knowledge');
        document.getElementById('kb-modal-question').value = '';
        document.getElementById('kb-modal-answer').value = '';
        document.getElementById('kb-modal-title').value = item.title || '';
        document.getElementById('kb-modal-content').value = item.content || '';
      }
      document.getElementById('kb-modal-tags').value = (item.tags || []).join(',');
      document.getElementById('knowledge-modal').classList.add('show');
    });
}
async function saveKnowledge() {
  const id = document.getElementById('kb-edit-id').value;
  const collection = document.getElementById('kb-modal-collection').value;
  const tags = document.getElementById('kb-modal-tags').value.split(',').map(t => t.trim()).filter(Boolean);
  const mode = document.querySelector('input[name="kb-mode"]:checked').value;
  let body = { tags, collection };
  if (mode === 'qa') {
    const question = document.getElementById('kb-modal-question').value.trim();
    const answer = document.getElementById('kb-modal-answer').value.trim();
    if (!question || !answer) { toast('问题和答案不能为空', 'error'); return; }
    body.question = question;
    body.answer = answer;
  } else {
    const title = document.getElementById('kb-modal-title').value.trim();
    const content = document.getElementById('kb-modal-content').value.trim();
    if (!title || !content) { toast('标题和内容不能为空', 'error'); return; }
    body.title = title;
    body.content = content;
  }
  try {
    if (id) {
      await fetch(`${API}/knowledge/${id}?collection=${collection}`, {
        method: 'PUT', headers: {'Content-Type':'application/json; charset=utf-8'},
        body: JSON.stringify(body)
      });
      toast('知识点已更新');
    } else {
      await fetch(`${API}/knowledge`, {
        method: 'POST', headers: {'Content-Type':'application/json; charset=utf-8'},
        body: JSON.stringify(body)
      });
      toast('知识点已新增');
    }
    closeModal('knowledge-modal');
    loadKnowledge();
  } catch(e) { toast('保存失败', 'error'); }
}
async function deleteKnowledge(id, collection) {
  if (!confirm('确认删除这条知识点？')) return;
  await fetch(`${API}/knowledge/${id}?collection=${collection}`, {method:'DELETE'});
  toast('已删除');
  loadKnowledge();
}
function openBatchModal() {
  document.getElementById('batch-collection').value = document.getElementById('kb-collection').value;
  document.getElementById('batch-data').value = '';
  document.getElementById('batch-modal').classList.add('show');
}
async function batchIngest() {
  const collection = document.getElementById('batch-collection').value;
  const raw = document.getElementById('batch-data').value.trim();
  if (!raw) { toast('请输入数据', 'error'); return; }
  const records = [];
  for (const line of raw.split('\\n')) {
    const l = line.trim();
    if (!l) continue;
    try { records.push(JSON.parse(l)); }
    catch(e) { toast('第' + (records.length+1) + '行JSON格式错误', 'error'); return; }
  }
  try {
    const res = await fetch(`${API}/knowledge/ingest`, {
      method: 'POST', headers: {'Content-Type':'application/json; charset=utf-8'},
      body: JSON.stringify({collection, records})
    });
    const data = await res.json();
    toast(`成功导入 ${data.ingested} 条`);
    closeModal('batch-modal');
    loadKnowledge();
  } catch(e) { toast('导入失败', 'error'); }
}

// ===== 会话记录 =====
async function loadSessions() {
  const platform = document.getElementById('session-platform').value;
  const res = await fetch(`${API}/sessions?platform=${platform}&limit=${PAGE_SIZE}&offset=${sessOffset}`);
  const data = await res.json();
  const tbody = document.getElementById('session-table-body');
  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">暂无会话记录，点击右上角录入</td></tr>';
  } else {
    tbody.innerHTML = data.items.map(s => `
      <tr>
        <td>${escapeHtml(s.buyer_id)}</td>
        <td><span class="tag">${escapeHtml(s.platform)}</span></td>
        <td>${escapeHtml(s.shop_id || '-')}</td>
        <td>${s.message_count}</td>
        <td>${new Date(s.created_at).toLocaleString('zh-CN')}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="viewSession('${s.id}')">查看</button>
          <button class="btn btn-danger" onclick="deleteSession('${s.id}')">删除</button>
        </td>
      </tr>`).join('');
  }
  renderPagination('session-pagination', data.total, sessOffset, (newOffset) => { sessOffset = newOffset; loadSessions(); });
}
function openSessionModal() {
  document.getElementById('sess-buyer-id').value = '';
  document.getElementById('sess-platform').value = 'doudian';
  document.getElementById('sess-shop-id').value = '';
  document.getElementById('sess-messages').value = '';
  document.getElementById('session-modal').classList.add('show');
}
async function saveSession() {
  const buyer_id = document.getElementById('sess-buyer-id').value.trim();
  const platform = document.getElementById('sess-platform').value;
  const shop_id = document.getElementById('sess-shop-id').value.trim();
  const raw = document.getElementById('sess-messages').value.trim();
  if (!buyer_id) { toast('买家ID不能为空', 'error'); return; }
  if (!raw) { toast('对话内容不能为空', 'error'); return; }
  const messages = [];
  for (const line of raw.split('\\n')) {
    const l = line.trim();
    if (!l) continue;
    const idx = l.indexOf('|');
    if (idx < 0) continue;
    messages.push({role: l.substring(0, idx).trim(), content: l.substring(idx+1).trim()});
  }
  if (!messages.length) { toast('未解析到有效消息', 'error'); return; }
  try {
    const res = await fetch(`${API}/sessions`, {
      method: 'POST', headers: {'Content-Type':'application/json; charset=utf-8'},
      body: JSON.stringify({buyer_id, platform, shop_id, messages})
    });
    const data = await res.json();
    toast(`已录入 ${data.message_count} 条消息`);
    closeModal('session-modal');
    loadSessions();
  } catch(e) { toast('录入失败', 'error'); }
}
async function viewSession(id) {
  try {
    const res = await fetch(`${API}/sessions/${id}`);
    const data = await res.json();
    const body = document.getElementById('session-detail-body');
    let html = `<div style="margin-bottom:12px;font-size:13px;color:var(--text-muted)">买家: ${escapeHtml(data.buyer_id)} | 平台: ${escapeHtml(data.platform)} | 消息: ${data.message_count}条</div>`;
    html += '<div>';
    for (const m of data.messages) {
      const isUser = m.role === 'user';
      html += `<div class="message-bubble ${isUser ? 'message-user' : 'message-assistant'}">
        <div class="message-role">${isUser ? '买家' : '客服'}</div>
        <div>${escapeHtml(m.content)}</div>
      </div>`;
    }
    html += '</div>';
    body.innerHTML = html;
    document.getElementById('session-detail-modal').classList.add('show');
  } catch(e) { toast('加载失败', 'error'); }
}
async function deleteSession(id) {
  if (!confirm('确认删除这条会话记录？')) return;
  await fetch(`${API}/sessions/${id}`, {method:'DELETE'});
  toast('已删除');
  loadSessions();
}

// ===== 测试问答 =====
let pgHistory = [];

async function loadQuickQuestions() {
  // 从 FAQ 知识库中取几条问题作为快捷入口
  try {
    const res = await fetch(API + '/knowledge?collection=kb_faq&limit=8&offset=0');
    const data = await res.json();
    const container = document.getElementById('pg-quick-questions');
    if (!data.items.length) {
      container.innerHTML = '<span style="font-size:13px;color:var(--text-muted)">知识库暂无FAQ，请先录入</span>';
      return;
    }
    container.innerHTML = data.items.filter(item => item.question).map(item =>
      `<span class="tag" style="cursor:pointer;padding:6px 12px;font-size:13px" onclick="useQuickQuestion('${escapeAttr(item.question)}')">${escapeHtml(item.question.substring(0, 30))}${item.question.length > 30 ? '...' : ''}</span>`
    ).join('');
    if (!container.innerHTML) {
      container.innerHTML = '<span style="font-size:13px;color:var(--text-muted)">知识库暂无QA问答，请先录入</span>';
    }
  } catch(e) {
    document.getElementById('pg-quick-questions').innerHTML = '<span style="font-size:13px;color:var(--text-muted)">加载失败</span>';
  }
}

function useQuickQuestion(q) {
  document.getElementById('pg-question').value = q;
  document.getElementById('pg-question').focus();
}

async function askQuestion() {
  const question = document.getElementById('pg-question').value.trim();
  if (!question) { toast('请输入问题', 'error'); return; }

  const btn = document.getElementById('pg-submit-btn');
  const status = document.getElementById('pg-status');
  btn.disabled = true;
  btn.textContent = '⏳ 思考中...';
  status.textContent = '正在检索知识库并生成回答...';

  const startTime = Date.now();

  try {
    const res = await fetch('/api/qa', {
      method: 'POST',
      headers: {'Content-Type': 'application/json; charset=utf-8'},
      body: JSON.stringify({question: question})
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error('HTTP ' + res.status + ': ' + errText);
    }

    const data = await res.json();
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);

    // 渲染回答
    const answerArea = document.getElementById('pg-answer-area');
    const matchBadge = document.getElementById('pg-match-badge');

    if (data.matched) {
      matchBadge.style.display = 'inline-block';
      matchBadge.className = 'tag';
      matchBadge.style.background = '#e6f4ea';
      matchBadge.style.color = 'var(--success)';
      matchBadge.textContent = '✓ 命中知识库';
    } else {
      matchBadge.style.display = 'inline-block';
      matchBadge.className = 'tag';
      matchBadge.style.background = '#fce8e6';
      matchBadge.style.color = 'var(--danger)';
      matchBadge.textContent = '✗ 未命中';
    }

    answerArea.innerHTML = `
      <div style="font-size:15px;line-height:1.8;white-space:pre-wrap;">${escapeHtml(data.answer)}</div>
      <div style="margin-top:12px;font-size:12px;color:var(--text-muted)">耗时 ${elapsed}s · 来源 ${data.sources.length} 条</div>
    `;

    // 渲染匹配来源
    const sourcesArea = document.getElementById('pg-sources-area');
    if (!data.sources.length) {
      sourcesArea.innerHTML = '<div class="empty">未匹配到知识库片段</div>';
    } else {
      sourcesArea.innerHTML = data.sources.map((s, i) => {
        const score = (s.score * 100).toFixed(1);
        const scoreColor = s.score > 0.8 ? 'var(--success)' : s.score > 0.5 ? '#e8a317' : 'var(--danger)';
        return `
          <div style="padding:12px;border:1px solid var(--border);border-radius:var(--radius);margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
              <span style="font-weight:600;font-size:13px;">片段 ${i + 1}</span>
              <span style="font-size:12px;color:${scoreColor};font-weight:600;">相似度 ${score}%</span>
            </div>
            <div style="font-size:13px;color:var(--text-muted);white-space:pre-wrap;line-height:1.6;">${escapeHtml(s.text)}</div>
          </div>
        `;
      }).join('');
    }

    // 添加到历史
    pgHistory.unshift({question, answer: data.answer, matched: data.matched, sources: data.sources.length, elapsed});
    renderHistory();

    status.textContent = '';
  } catch(e) {
    status.textContent = '';
    const answerArea = document.getElementById('pg-answer-area');
    answerArea.innerHTML = `
      <div style="padding:16px;background:#fce8e6;border-radius:var(--radius);color:var(--danger);">
        <div style="font-weight:600;margin-bottom:8px;">❌ 请求失败</div>
        <div style="font-size:13px;">${escapeHtml(e.message)}</div>
        <div style="font-size:12px;margin-top:8px;color:var(--text-muted)">请检查 LLM 配置（DEEPSEEK_API_KEY 和 DEEPSEEK_MODEL）是否正确</div>
      </div>
    `;
    toast('问答请求失败', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 发送提问';
  }
}

function clearPlayground() {
  document.getElementById('pg-question').value = '';
  document.getElementById('pg-answer-area').innerHTML = '<div class="empty">在左侧输入问题后点击"发送提问"查看回答</div>';
  document.getElementById('pg-sources-area').innerHTML = '<div class="empty">提问后将展示命中的知识库片段</div>';
  document.getElementById('pg-match-badge').style.display = 'none';
  document.getElementById('pg-status').textContent = '';
}

function renderHistory() {
  const area = document.getElementById('pg-history-area');
  if (!pgHistory.length) {
    area.innerHTML = '<div class="empty" style="padding:20px">暂无测试记录</div>';
    return;
  }
  area.innerHTML = pgHistory.map(h => `
    <div style="padding:12px 20px;border-bottom:1px solid var(--border);">
      <div style="font-size:13px;font-weight:600;margin-bottom:4px;">Q: ${escapeHtml(h.question)}</div>
      <div style="font-size:13px;color:var(--text-muted);margin-bottom:4px;">A: ${escapeHtml(h.answer.substring(0, 100))}${h.answer.length > 100 ? '...' : ''}</div>
      <div style="font-size:12px;color:var(--text-muted)">
        ${h.matched ? '<span style="color:var(--success)">✓ 命中</span>' : '<span style="color:var(--danger)">✗ 未命中</span>'}
        · 来源 ${h.sources} 条 · ${h.elapsed}s
      </div>
    </div>
  `).join('');
}

function clearHistory() {
  pgHistory = [];
  renderHistory();
}

function escapeAttr(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ===== 工具函数 =====
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function renderPagination(containerId, total, offset, onChange) {
  const container = document.getElementById(containerId);
  if (total <= PAGE_SIZE) { container.innerHTML = ''; return; }
  const pages = Math.ceil(total / PAGE_SIZE);
  const current = Math.floor(offset / PAGE_SIZE);
  let html = '';
  html += `<button class="pager-btn" ${current===0?'disabled':''} onclick="void(0)" data-page="${current-1}">上一页</button>`;
  for (let i = 0; i < pages; i++) {
    if (i === 0 || i === pages-1 || Math.abs(i-current) <= 2) {
      html += `<button class="pager-btn ${i===current?'active':''}" data-page="${i}">${i+1}</button>`;
    } else if (Math.abs(i-current) === 3) {
      html += '<span style="padding:6px">...</span>';
    }
  }
  html += `<button class="pager-btn" ${current>=pages-1?'disabled':''} data-page="${current+1}">下一页</button>`;
  container.innerHTML = html;
  container.querySelectorAll('.pager-btn[data-page]').forEach(btn => {
    btn.addEventListener('click', function() {
      const page = parseInt(this.dataset.page);
      if (page >= 0 && page < pages) onChange(page * PAGE_SIZE);
    });
  });
}

// 初始加载
loadStats();

// ===== 批量测试 =====
let btCurrentTaskId = null;
let btFilter = '';
let btOffset = 0;
let btPollTimer = null;

async function uploadExcel() {
  const input = document.getElementById('bt-file-input');
  if (!input.files.length) return;
  const file = input.files[0];
  input.value = '';
  const formData = new FormData();
  formData.append('file', file);
  try {
    const res = await fetch(`${API}/batch-test/upload`, { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) { toast(data.detail || '上传失败', 'error'); return; }
    toast(`已解析 ${data.total} 条问题`);
    // 自动开始测试
    await runBatchTest(data.task_id, data.filename);
  } catch(e) { toast('上传失败', 'error'); }
}

async function downloadTemplate() {
  window.open(`${API}/batch-test/template`, '_blank');
}

async function runBatchTest(taskId, filename) {
  try {
    const res = await fetch(`${API}/batch-test/${taskId}/run`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) { toast(data.detail || '启动失败', 'error'); return; }
    toast('批量测试已启动...');
    loadBtTasks();
    // 打开结果弹窗并轮询
    btCurrentTaskId = taskId;
    document.getElementById('bt-modal-filename').textContent = filename || '';
    openModal('bt-result-modal');
    pollBtResults();
  } catch(e) { toast('启动失败', 'error'); }
}

async function loadBtTasks() {
  try {
    const res = await fetch(`${API}/batch-test?limit=50`);
    const data = await res.json();
    const tbody = document.getElementById('bt-task-list');
    if (!data.items.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">暂无测试任务，请上传 Excel</td></tr>';
      return;
    }
    tbody.innerHTML = data.items.map(t => {
      const progress = t.total > 0 ? Math.round(t.completed / t.total * 100) : 0;
      const statusText = { pending: '等待中', running: '运行中', completed: '已完成', failed: '失败' }[t.status] || t.status;
      const accText = t.accuracy !== null ? `${t.accuracy}%` : '-';
      const time = t.created_at ? new Date(t.created_at).toLocaleString('zh-CN') : '-';
      return `<tr>
        <td>${escapeHtml(t.filename)}</td>
        <td>${t.completed}/${t.total} (${progress}%)</td>
        <td><span class="tag">${statusText}</span></td>
        <td>${t.reviewed}/${t.total}</td>
        <td>${accText}</td>
        <td style="font-size:13px">${time}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="viewBtResults('${t.id}','${escapeAttr(t.filename)}')">查看结果</button>
          ${t.status === 'pending' || t.status === 'failed' ? `<button class="btn btn-primary btn-sm" onclick="runBatchTest('${t.id}','${escapeAttr(t.filename)}')">${t.status === 'failed' ? '重新测试' : '开始测试'}</button>` : ''}
          <button class="btn btn-danger" onclick="deleteBtTask('${t.id}')">删除</button>
        </td>
      </tr>`;
    }).join('');
  } catch(e) { /* ignore */ }
}

async function viewBtResults(taskId, filename) {
  btCurrentTaskId = taskId;
  btFilter = '';
  btOffset = 0;
  document.querySelectorAll('.bt-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === ''));
  document.getElementById('bt-modal-filename').textContent = filename || '';
  openModal('bt-result-modal');
  await loadBtResults();
  // 如果任务还在运行，开始轮询
  const status = await fetch(`${API}/batch-test/${taskId}/status`).then(r => r.json());
  if (status.status === 'running') pollBtResults();
}

async function loadBtResults() {
  if (!btCurrentTaskId) return;
  try {
    const [statusRes, resultsRes] = await Promise.all([
      fetch(`${API}/batch-test/${btCurrentTaskId}/status`),
      fetch(`${API}/batch-test/${btCurrentTaskId}/results?limit=${PAGE_SIZE}&offset=${btOffset}&review_filter=${btFilter}`)
    ]);
    const status = await statusRes.json();
    const data = await resultsRes.json();

    // 渲染进度条
    const pb = document.getElementById('bt-progress-bar');
    const progress = status.total > 0 ? Math.round(status.completed / status.total * 100) : 0;
    pb.innerHTML = `
      <div style="display:flex;gap:16px;font-size:13px;color:var(--text-muted);margin-bottom:8px;">
        <span>进度: ${status.completed}/${status.total} (${progress}%)</span>
        <span>命中: ${status.matched}</span>
        <span>未命中: ${status.unmatched}</span>
        <span>错误: ${status.errors}</span>
        <span style="color:var(--success)">正确: ${status.correct}</span>
        <span style="color:var(--danger)">错误: ${status.incorrect}</span>
        <span>待审核: ${status.pending_review}</span>
      </div>
      <div style="height:6px;background:var(--border);border-radius:3px;overflow:hidden">
        <div style="height:100%;width:${progress}%;background:var(--primary);transition:width .3s"></div>
      </div>
    `;

    // 渲染结果
    const tbody = document.getElementById('bt-results-body');
    if (!data.items.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>';
    } else {
      tbody.innerHTML = data.items.map(it => {
        const matchedBadge = it.matched === true
          ? '<span style="color:var(--success)">✓ 命中</span>'
          : it.matched === false
            ? '<span style="color:var(--danger)">✗ 未命中</span>'
            : '<span style="color:var(--text-muted)">—</span>';
        const time = it.response_time_ms !== null ? `${it.response_time_ms}ms` : '—';
        let reviewBtn = '';
        if (it.test_status === 'done') {
          const isCorrect = it.review_status === 'correct';
          const isIncorrect = it.review_status === 'incorrect';
          reviewBtn = `
            <button class="btn btn-sm ${isCorrect ? 'btn-primary' : 'btn-outline'}" style="padding:2px 8px;font-size:12px" onclick="reviewItem(${it.id},'correct')">✓ 正确</button>
            <button class="btn btn-sm ${isIncorrect ? 'btn-danger' : 'btn-outline'}" style="padding:2px 8px;font-size:12px" onclick="reviewItem(${it.id},'incorrect')">✗ 错误</button>
          `;
        } else if (it.test_status === 'error') {
          reviewBtn = `<span style="color:var(--danger);font-size:12px">测试出错</span>`;
        } else {
          reviewBtn = '<span style="color:var(--text-muted);font-size:12px">排队中</span>';
        }
        const reasonInput = it.review_status === 'incorrect'
          ? `<input type="text" class="form-input" style="margin-top:4px;font-size:12px;padding:2px 6px" placeholder="未答对原因..." value="${escapeAttr(it.review_reason||'')}" onchange="saveReason(${it.id}, this.value)" onclick="event.stopPropagation()">`
          : '';
        const actualAns = it.actual_answer
          ? escapeHtml(it.actual_answer.length > 80 ? it.actual_answer.substring(0,80)+'...' : it.actual_answer)
          : (it.test_status === 'error' ? `<span style="color:var(--danger)">${escapeHtml(it.error_msg||'错误')}</span>` : '—');
        const expectedAns = it.expected_answer ? escapeHtml(it.expected_answer.length > 60 ? it.expected_answer.substring(0,60)+'...' : it.expected_answer) : '—';

        return `<tr style="border-bottom:1px solid var(--border)">
          <td>${it.seq}</td>
          <td style="font-size:13px">${escapeHtml(it.question)}</td>
          <td style="font-size:13px">${actualAns}</td>
          <td style="font-size:13px;color:var(--text-muted)">${expectedAns}</td>
          <td style="font-size:13px">${matchedBadge}</td>
          <td style="font-size:12px;color:var(--text-muted)">${time}</td>
          <td>
            <div style="display:flex;gap:4px;flex-wrap:wrap">${reviewBtn}</div>
            ${reasonInput}
          </td>
        </tr>`;
      }).join('');
    }

    // 分页
    renderPagination('bt-pagination', data.total, btOffset, (newOffset) => { btOffset = newOffset; loadBtResults(); });
  } catch(e) { /* ignore */ }
}

function pollBtResults() {
  if (btPollTimer) clearInterval(btPollTimer);
  btPollTimer = setInterval(async () => {
    await loadBtResults();
    await loadBtTasks();
    try {
      const res = await fetch(`${API}/batch-test/${btCurrentTaskId}/status`);
      const status = await res.json();
      if (status.status !== 'running') {
        clearInterval(btPollTimer);
        btPollTimer = null;
        toast('批量测试已完成');
      }
    } catch(e) {}
  }, 3000);
}

function btSetFilter(filter) {
  btFilter = filter;
  btOffset = 0;
  document.querySelectorAll('.bt-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === filter));
  loadBtResults();
}

async function reviewItem(itemId, status) {
  try {
    await fetch(`${API}/batch-test/items/${itemId}`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json; charset=utf-8'},
      body: JSON.stringify({ review_status: status })
    });
    loadBtResults();
    loadBtTasks();
  } catch(e) { toast('操作失败', 'error'); }
}

async function saveReason(itemId, reason) {
  try {
    await fetch(`${API}/batch-test/items/${itemId}`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json; charset=utf-8'},
      body: JSON.stringify({ review_status: 'incorrect', review_reason: reason })
    });
    toast('原因已保存');
  } catch(e) { /* ignore */ }
}

async function deleteBtTask(taskId) {
  if (!confirm('确认删除此测试任务及所有结果？')) return;
  try {
    await fetch(`${API}/batch-test/${taskId}`, { method: 'DELETE' });
    toast('已删除');
    loadBtTasks();
  } catch(e) { toast('删除失败', 'error'); }
}

function exportResults() {
  if (!btCurrentTaskId) return;
  window.open(`${API}/batch-test/${btCurrentTaskId}/export`, '_blank');
}
</script>
</body>
</html>"""
