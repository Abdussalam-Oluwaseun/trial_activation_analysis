/**
 * COGENT bi — Trial Activation Dashboard
 * app.js — SPA router, API layer, view renderers
 */

/* ── Config ─────────────────────────────────────────────────────────────────── */
const API_BASE = '';   // Same origin; uvicorn serves both API + static

/* ── State ──────────────────────────────────────────────────────────────────── */
const state = {
  currentView: 'overview',
  orgs: { list: [], total: 0, page: 1, filter: 'All', search: '', selectedId: null },
  funnel: { activeGoal: 'G1' },
  recs: { filter: 'All' },
  charts: {},
};

/* ── API helpers ─────────────────────────────────────────────────────────────── */
async function apiFetch(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Router ──────────────────────────────────────────────────────────────────── */
function navigate(view) {
  state.currentView = view;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.view === view);
  });
  renderView(view);
}

/* ── View dispatcher ─────────────────────────────────────────────────────────── */
async function renderView(view) {
  const content = document.getElementById('page-content');
  const header  = document.getElementById('page-header');

  content.innerHTML = '<div class="state-loading">Loading…</div>';

  const views = {
    overview:        renderOverview,
    funnel:          renderFunnel,
    organisations:   renderOrganisations,
    recommendations: renderRecommendations,
  };

  try {
    await (views[view] || renderOverview)(header, content);
  } catch (err) {
    content.innerHTML = `<div class="state-error">Failed to load data: ${err.message}</div>`;
  }
}

/* ══════════════════════════════════════════════════════════════════════════════
   VIEW 1 — OVERVIEW
══════════════════════════════════════════════════════════════════════════════ */
async function renderOverview(header, content) {
  setHeader(header, 'Overview', 'Monitor trial activation, conversion and organisation health.');

  const data = await apiFetch('/api/overview');
  const k = data.kpis;

  content.innerHTML = `
    <!-- KPI row -->
    <div class="kpi-row">
      ${kpiBlock(k.total_orgs.toLocaleString(), 'Total organisations', '', '')}
      ${kpiBlock(k.conversion_rate + '%', 'Conversion rate', '+2.4%', 'up')}
      ${kpiBlock(k.activation_rate + '%', 'Activation rate', '+1.8%', 'up')}
      ${kpiBlock((k.avg_days_to_convert ?? '—') + (k.avg_days_to_convert ? ' days' : ''), 'Avg. days to convert', '↓ 1.2 days', 'down')}
    </div>

    <!-- Charts row -->
    <div class="charts-row">
      <div class="card" id="card-conversion">
        <div class="card-title">Conversion</div>
        ${conversionBar(k.converted_orgs, k.total_orgs - k.converted_orgs, k.conversion_rate)}
      </div>
      <div class="card" id="card-goals">
        <div class="card-title">Goal completion</div>
        <div class="goal-bar-list" id="goal-bars"></div>
      </div>
    </div>

    <!-- Recent orgs table -->
    <div class="card">
      <div class="card-title">
        Recent organisations
        <a href="#" id="view-all-link">View all →</a>
      </div>
      <div id="recent-orgs-wrap">
        <div class="state-loading">Loading…</div>
      </div>
    </div>
  `;

  // Render goal bars
  const barsEl = document.getElementById('goal-bars');
  const minRate = Math.min(...data.goal_completion.map(g => g.completion_rate));
  barsEl.innerHTML = data.goal_completion.map(g => {
    const isLow = g.completion_rate === minRate;
    return `
      <div class="goal-bar-item">
        <span class="goal-bar-label">${g.goal_id}</span>
        <div class="goal-bar-track">
          <div class="goal-bar-fill ${isLow ? 'highlight' : ''}" style="width:${g.completion_rate}%"></div>
        </div>
        <span class="goal-bar-pct">${g.completion_rate}%</span>
      </div>
    `;
  }).join('');

  // View all link
  document.getElementById('view-all-link').addEventListener('click', e => {
    e.preventDefault();
    navigate('organisations');
  });

  // Fetch recent orgs
  try {
    const orgsData = await apiFetch('/api/organisations?page=1&page_size=8');
    document.getElementById('recent-orgs-wrap').innerHTML = orgTable(orgsData.organisations, true);
    document.querySelectorAll('[data-org-id]').forEach(el => {
      el.addEventListener('click', () => {
        state.orgs.selectedId = el.dataset.orgId;
        navigate('organisations');
      });
    });
  } catch {
    document.getElementById('recent-orgs-wrap').innerHTML =
      '<div class="state-error">Could not load recent organisations.</div>';
  }
}

function kpiBlock(value, label, trend, trendClass) {
  const trendHtml = trend
    ? `<div class="kpi-trend ${trendClass}">${trend}</div>`
    : '';
  return `
    <div class="kpi-block">
      <div class="kpi-value">${value}</div>
      <div class="kpi-label">${label}</div>
      ${trendHtml}
    </div>
  `;
}

function conversionBar(converted, notConverted, rate) {
  return `
    <div class="conversion-bar-wrap">
      <div class="conv-segment converted" style="flex:${rate}">${rate}%</div>
      <div class="conv-segment not-converted" style="flex:${100 - rate}">${100 - rate}%</div>
    </div>
    <div class="conversion-legend">
      <div class="legend-row">
        <span><span class="legend-dot" style="background:var(--accent)"></span>Converted</span>
        <span class="legend-count">${converted.toLocaleString()}</span>
      </div>
      <div class="legend-row">
        <span><span class="legend-dot" style="background:#3a3935"></span>Not converted</span>
        <span class="legend-count">${notConverted.toLocaleString()}</span>
      </div>
    </div>
  `;
}

function orgTable(orgs, compact = false) {
  if (!orgs.length) return '<div class="empty-state"><p>No organisations found.</p></div>';
  return `
    <table class="data-table">
      <thead>
        <tr>
          <th>Org ID</th>
          <th>Goal progress</th>
          <th>Status</th>
          ${compact ? '' : '<th>Active days</th>'}
          <th style="text-align:right">Trial end</th>
        </tr>
      </thead>
      <tbody>
        ${orgs.map(o => `
          <tr data-org-id="${o.organization_id}">
            <td style="font-weight:600">${o.organization_id}</td>
            <td>${inlineProgress(o.goals_completed, 5)}</td>
            <td>${statusChip(o.status)}</td>
            ${compact ? '' : `<td>${o.active_days} days</td>`}
            <td style="text-align:right;color:var(--text-secondary);font-size:12.5px">${o.trial_end || '—'}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function inlineProgress(done, total) {
  const pct = (done / total) * 100;
  const cls = done === total ? 'full' : done >= 3 ? 'almost' : 'low';
  return `
    <div class="prog-bar">
      <div class="prog-track"><div class="prog-fill ${cls}" style="width:${pct}%"></div></div>
      <span class="prog-label">${done} / ${total}</span>
    </div>
  `;
}

function statusChip(status) {
  const map = {
    Converted: 'converted',
    Activated: 'activated',
    'At Risk': 'at-risk',
    Trial: 'trial',
    Churned: 'churned',
  };
  return `<span class="chip ${map[status] || 'trial'}">${status}</span>`;
}

/* ══════════════════════════════════════════════════════════════════════════════
   VIEW 2 — GOAL FUNNEL
══════════════════════════════════════════════════════════════════════════════ */
async function renderFunnel(header, content) {
  setHeader(header, 'Goal Funnel', 'Track how organisations progress through each trial goal.');

  const data = await apiFetch('/api/funnel');

  content.innerHTML = `
    <div class="funnel-layout">
      <div>
        <div class="card" style="padding:0;overflow:hidden">
          <div id="funnel-stages"></div>
        </div>
      </div>
      <div>
        <div class="funnel-deep-dive" id="deep-dive-panel"></div>
        <div style="margin-top:16px">
          <div class="card-title" style="font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">
            Drop-off insights
          </div>
          <div class="drop-insights" id="drop-insights"></div>
        </div>
      </div>
    </div>
  `;

  // Render funnel stages
  renderFunnelStages(data, state.funnel.activeGoal);

  // Render insights
  const insightsEl = document.getElementById('drop-insights');
  insightsEl.innerHTML = data.dropoff_insights.map(ins => `
    <div class="drop-insight">
      <strong>${ins.stage}:</strong> ${ins.message}
    </div>
  `).join('');

  // Activate default deep-dive
  renderDeepDive(data.deep_dive.find(d => d.goal_id === state.funnel.activeGoal) || data.deep_dive[0]);
}

function renderFunnelStages(data, activeId) {
  const el = document.getElementById('funnel-stages');
  el.innerHTML = data.stages.map((s, i) => {
    const isActive = s.goal_id === activeId;
    const connector = s.continued_rate != null ? `
      <div class="funnel-connector">
        <div style="width:1px;height:16px;background:var(--border);margin-left:10px"></div>
        <span style="margin-left:8px">${s.continued_rate}% continued ↓</span>
      </div>
    ` : '';

    return `
      <div class="funnel-stage ${isActive ? 'active' : ''}" data-goal="${s.goal_id}">
        <span class="funnel-stage-id">${s.goal_id}</span>
        <div class="funnel-stage-info">
          <div class="funnel-stage-label">${s.goal_label}</div>
          <div class="funnel-stage-desc">${s.goal_description}</div>
        </div>
        <div class="funnel-bar-wrap">
          <div class="funnel-bar-track">
            <div class="funnel-bar-fill" style="width:${s.completion_rate}%"></div>
          </div>
          <div class="funnel-bar-meta">
            <span>${s.completed_orgs.toLocaleString()} orgs</span>
            <span>${s.completion_rate}%</span>
          </div>
        </div>
      </div>
      ${i < data.stages.length - 1 ? `
        <div class="funnel-connector" style="padding-left:52px;padding-bottom:2px">
          <div style="display:flex;flex-direction:column;align-items:flex-start">
            <div style="width:1px;height:10px;background:var(--border)"></div>
            <span style="font-size:11.5px;color:var(--text-secondary);margin-top:2px">
              ${s.continued_rate != null ? s.continued_rate + '% continued ↓' : ''}
            </span>
          </div>
        </div>
      ` : ''}
    `;
  }).join('');

  document.querySelectorAll('.funnel-stage').forEach(el => {
    el.addEventListener('click', () => {
      const goalId = el.dataset.goal;
      state.funnel.activeGoal = goalId;
      document.querySelectorAll('.funnel-stage').forEach(s => s.classList.remove('active'));
      el.classList.add('active');
      // Update bar fill colour
      document.querySelectorAll('.funnel-bar-fill').forEach(f => f.style.background = 'var(--data-bar)');
      el.querySelector('.funnel-bar-fill').style.background = 'var(--accent)';
      const dd = document.querySelector(`[data-goal="${goalId}"]`);
      // Refresh deep dive
      const deepDiveData = window._funnelData?.deep_dive.find(d => d.goal_id === goalId);
      if (deepDiveData) renderDeepDive(deepDiveData);
    });
  });

  // Store data for click handler access
  window._funnelData = { deep_dive: [] };
}

function renderDeepDive(dd) {
  if (!dd) return;
  const el = document.getElementById('deep-dive-panel');
  el.innerHTML = `
    <div class="dive-metric">
      <div class="dive-value">${dd.completion_rate}%</div>
      <div class="dive-label">Completion rate</div>
    </div>
    <div class="dive-metric">
      <div class="dive-value">${dd.median_days_to_complete != null ? dd.median_days_to_complete + ' days' : '—'}</div>
      <div class="dive-label">Median days to complete</div>
    </div>
    <div class="dive-metric">
      <div class="dive-value danger">↓ ${dd.dropoff_to_next != null ? dd.dropoff_to_next + '%' : '—'}</div>
      <div class="dive-label">Drop-off to next goal</div>
    </div>
    <div class="dive-metric">
      <div class="dive-value">${dd.pct_of_activated}%</div>
      <div class="dive-label">Of fully activated orgs</div>
    </div>
  `;
  window._funnelData = window._funnelData || {};
  if (!window._funnelData.deep_dive) window._funnelData.deep_dive = [];
  // Update existing or push
  const idx = window._funnelData.deep_dive.findIndex(d => d.goal_id === dd.goal_id);
  if (idx >= 0) window._funnelData.deep_dive[idx] = dd;
  else window._funnelData.deep_dive.push(dd);
}

/* ══════════════════════════════════════════════════════════════════════════════
   VIEW 3 — ORGANISATIONS
══════════════════════════════════════════════════════════════════════════════ */
async function renderOrganisations(header, content) {
  setHeader(header, 'Organisations', 'Track each organisation\'s journey through the trial.');

  content.innerHTML = `
    <div class="orgs-layout">
      <!-- Left panel -->
      <div class="org-list-panel">
        <div class="org-list-header">
          <h3>Organisations</h3>
          <div class="org-filter-tabs" id="org-filter-tabs">
            ${['All','Activated','At Risk','Converted'].map(f =>
              `<button class="${f === state.orgs.filter ? 'active' : ''}" data-filter="${f}">${f}</button>`
            ).join('')}
          </div>
        </div>
        <div class="org-search-wrap">
          <input class="org-search-input" id="org-search" placeholder="Search organisations…"
            value="${state.orgs.search}" autocomplete="off" />
        </div>
        <div class="org-list-items" id="org-list-items">
          <div class="state-loading">Loading…</div>
        </div>
      </div>

      <!-- Right panel -->
      <div class="org-detail-panel" id="org-detail-panel">
        <div class="org-detail-empty">Select an organisation to view details.</div>
      </div>
    </div>
  `;

  await loadOrgList();

  // Filter buttons
  document.querySelectorAll('#org-filter-tabs button').forEach(btn => {
    btn.addEventListener('click', () => {
      state.orgs.filter = btn.dataset.filter;
      state.orgs.page = 1;
      document.querySelectorAll('#org-filter-tabs button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadOrgList();
    });
  });

  // Search with debounce
  let searchTimer;
  document.getElementById('org-search').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.orgs.search = e.target.value;
      state.orgs.page = 1;
      loadOrgList();
    }, 300);
  });

  // If coming from overview with a pre-selected org
  if (state.orgs.selectedId) {
    loadOrgDetail(state.orgs.selectedId);
    state.orgs.selectedId = null;
  }
}

async function loadOrgList() {
  const listEl = document.getElementById('org-list-items');
  if (!listEl) return;
  listEl.innerHTML = '<div class="state-loading">Loading…</div>';

  const filterParam = state.orgs.filter !== 'All' ? `&status=${encodeURIComponent(state.orgs.filter)}` : '';
  const searchParam = state.orgs.search ? `&search=${encodeURIComponent(state.orgs.search)}` : '';
  const url = `/api/organisations?page=${state.orgs.page}&page_size=50${filterParam}${searchParam}`;

  try {
    const data = await apiFetch(url);
    state.orgs.list = data.organisations;
    state.orgs.total = data.total;

    if (!data.organisations.length) {
      listEl.innerHTML = '<div class="empty-state"><p>No organisations match this filter.</p></div>';
      return;
    }

    listEl.innerHTML = data.organisations.map(o => `
      <div class="org-list-item" data-org-id="${o.organization_id}">
        <div class="org-item-top">
          <span class="org-item-id">${o.organization_id}</span>
          <span class="org-item-status">${statusChip(o.status)}</span>
        </div>
        <div class="org-item-prog">${inlineProgress(o.goals_completed, 5)}</div>
      </div>
    `).join('');

    document.querySelectorAll('.org-list-item').forEach(el => {
      el.addEventListener('click', () => {
        document.querySelectorAll('.org-list-item').forEach(i => i.classList.remove('active'));
        el.classList.add('active');
        loadOrgDetail(el.dataset.orgId);
      });
    });
  } catch (err) {
    listEl.innerHTML = `<div class="state-error">${err.message}</div>`;
  }
}

async function loadOrgDetail(orgId) {
  const panel = document.getElementById('org-detail-panel');
  if (!panel) return;
  panel.innerHTML = '<div class="state-loading">Loading…</div>';

  try {
    const o = await apiFetch(`/api/organisations/${encodeURIComponent(orgId)}`);
    panel.innerHTML = orgDetailHTML(o);
  } catch (err) {
    panel.innerHTML = `<div class="state-error">${err.message}</div>`;
  }
}

function orgDetailHTML(o) {
  // Heatmap
  const maxEvents = Math.max(...o.heatmap.map(d => d.event_count), 1);
  const heatColors = ['#EEECE7', '#D9D6CF', '#B8B3AA', '#7E776E', '#C65D3A'];

  function heatColor(count) {
    if (count === 0) return heatColors[0];
    const ratio = count / maxEvents;
    if (ratio < 0.2) return heatColors[1];
    if (ratio < 0.4) return heatColors[2];
    if (ratio < 0.7) return heatColors[3];
    return heatColors[4];
  }

  const heatCells = o.heatmap.map(d => `
    <div class="heat-cell" style="background:${heatColor(d.event_count)}" title="Day ${d.day + 1}: ${d.event_count} events"></div>
  `).join('');

  // Module usage
  const maxModule = Math.max(...o.module_usage.map(m => m.event_count), 1);
  const moduleRows = o.module_usage.map(m => `
    <div class="module-row">
      <span class="module-name">${m.module}</span>
      <div class="module-bar-track">
        <div class="module-bar-fill" style="width:${(m.event_count / maxModule) * 100}%"></div>
      </div>
      <span class="module-count">${m.event_count.toLocaleString()}</span>
    </div>
  `).join('');

  // Goals
  const goalsHTML = o.goals.map(g => `
    <div class="goal-row">
      <span class="goal-icon">${g.is_completed ? '✅' : '○'}</span>
      <span class="goal-name ${g.is_completed ? '' : 'incomplete'}">${g.goal_label}</span>
      <span class="goal-evidence">${g.evidence}</span>
    </div>
  `).join('');

  // Recommendations (inline in detail)
  const recsHTML = o.recommendations.length ? `
    <div class="section-label" style="margin-top:22px;margin-bottom:10px">Recommendations</div>
    ${o.recommendations.map(r => `
      <div class="rec-card" style="margin-bottom:10px">
        <div class="rec-priority ${r.priority.toLowerCase()}">${r.priority} PRIORITY</div>
        <div class="rec-title">${r.title}</div>
        <div class="rec-body" style="margin-bottom:8px">${r.body}</div>
        <div class="rec-footer">
          <div>
            <span class="rec-action-label">Suggested action</span>
            <span class="rec-action">${r.suggested_action}</span>
          </div>
          <div class="rec-impact">
            <span class="impact-value">↗ ${r.expected_impact}</span>
          </div>
        </div>
      </div>
    `).join('')}
  ` : '';

  return `
    <div class="org-detail-header">
      <div>
        <div class="org-detail-id">${o.organization_id}</div>
      </div>
      <div>${statusChip(o.status)}</div>
    </div>
    <div class="org-detail-meta">
      <span>Trial started: <strong>${o.trial_start || '—'}</strong></span>
      <span>Trial ends: <strong>${o.trial_end || '—'}</strong></span>
      <span>${o.total_events.toLocaleString()} events</span>
      <span>${o.active_days} active days</span>
    </div>

    <div class="heatmap-section">
      <div class="section-label">Activity — last 30 days</div>
      <div class="heatmap-grid">${heatCells}</div>
      <div class="heat-legend">
        Less
        <div class="heat-legend-cells">
          ${heatColors.map(c => `<div class="heat-legend-cell" style="background:${c}"></div>`).join('')}
        </div>
        More
      </div>
    </div>

    <div class="goals-section">
      <div class="section-label">Goals — ${o.goals_completed} / 5 completed</div>
      ${goalsHTML}
    </div>

    <div class="module-section">
      <div class="section-label">Module usage</div>
      ${moduleRows || '<p style="color:var(--text-secondary);font-size:13px">No module data.</p>'}
    </div>

    ${recsHTML}
  `;
}

/* ══════════════════════════════════════════════════════════════════════════════
   VIEW 4 — RECOMMENDATIONS
══════════════════════════════════════════════════════════════════════════════ */
async function renderRecommendations(header, content) {
  setHeader(header, 'Recommendations', 'Next-best-action guidance for each organisation in trial.');

  content.innerHTML = `
    <div class="recs-filter-row" id="recs-filter-row">
      ${['All','High priority','Medium','Low'].map(f =>
        `<button class="filter-btn ${f === state.recs.filter ? 'active' : ''}" data-filter="${f}">${f}</button>`
      ).join('')}
    </div>
    <div id="recs-list"><div class="state-loading">Loading…</div></div>
  `;

  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      state.recs.filter = btn.dataset.filter;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadRecommendations();
    });
  });

  await loadRecommendations();
}

async function loadRecommendations() {
  const listEl = document.getElementById('recs-list');
  if (!listEl) return;

  // Determine which org status to show
  const filterStatusMap = {
    'All': null,
    'High priority': 'At Risk',
    'Medium': null,
    'Low': 'Activated',
  };

  const statusParam = filterStatusMap[state.recs.filter];
  const url = `/api/organisations?page_size=100${statusParam ? '&status=' + encodeURIComponent(statusParam) : ''}`;

  try {
    const orgsData = await apiFetch(url);

    // Fetch detail + recs for each org (batch, max 20)
    const orgs = orgsData.organisations.slice(0, 20);
    const detailPromises = orgs.map(o => apiFetch(`/api/organisations/${encodeURIComponent(o.organization_id)}`).catch(() => null));
    const details = (await Promise.all(detailPromises)).filter(Boolean);

    // Filter by priority if needed
    let cards = details.flatMap(o => o.recommendations.map(r => ({ org: o, rec: r })));

    if (state.recs.filter === 'High priority') {
      cards = cards.filter(c => c.rec.priority === 'HIGH');
    } else if (state.recs.filter === 'Medium') {
      cards = cards.filter(c => c.rec.priority === 'MEDIUM');
    } else if (state.recs.filter === 'Low') {
      cards = cards.filter(c => c.rec.priority === 'LOW');
    }

    // Sort: HIGH first, then MEDIUM, then LOW
    const pOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 };
    cards.sort((a, b) => pOrder[a.rec.priority] - pOrder[b.rec.priority]);

    if (!cards.length) {
      listEl.innerHTML = '<div class="empty-state"><p>No recommendations for this filter.</p></div>';
      return;
    }

    listEl.innerHTML = cards.map(({ org, rec }) => `
      <div class="rec-card">
        <div class="rec-card-top">
          <div>
            <div class="rec-priority ${rec.priority.toLowerCase()}">${rec.priority} PRIORITY</div>
            <div class="rec-org-id">${org.organization_id}</div>
            <div class="rec-org-meta">${inlineProgress(org.goals_completed, 5).replace('class="prog-bar"','class="prog-bar" style="display:inline-flex"')}</div>
          </div>
          ${statusChip(org.status)}
        </div>
        <hr class="rec-divider">
        <div class="rec-title">${rec.title}</div>
        <div class="rec-body">${rec.body}</div>
        <div class="rec-footer">
          <div>
            <span class="rec-action-label">Suggested action</span>
            <button class="rec-action" onclick="handleRecAction('${org.organization_id}', '${rec.suggested_action.replace(/'/g, "\\'")}')">
              ${rec.suggested_action}
            </button>
          </div>
          <div class="rec-impact">
            Expected impact: <span class="impact-value">&thinsp;↗ ${rec.expected_impact}</span>
          </div>
        </div>
      </div>
    `).join('');

  } catch (err) {
    listEl.innerHTML = `<div class="state-error">${err.message}</div>`;
  }
}

function handleRecAction(orgId, action) {
  // Placeholder: in production this would trigger a notification/CRM action
  alert(`Action queued for ${orgId}:\n"${action}"\n\n(In production, this would trigger your CRM or notification workflow.)`);
}

/* ── Shared helpers ──────────────────────────────────────────────────────────── */
function setHeader(headerEl, title, subtitle) {
  headerEl.innerHTML = `
    <div>
      <h1 class="page-title">${title}</h1>
      <p class="page-subtitle">${subtitle}</p>
    </div>
    <div class="header-right">
      <div id="global-search">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input type="text" placeholder="Search…" id="global-search-input">
        <span class="search-kbd">⌘K</span>
      </div>
      <div class="avatar">AJ</div>
    </div>
  `;
  const divider = document.querySelector('.header-divider');
  if (divider) divider.style.display = 'block';
}

/* ── Bootstrap ───────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => navigate(el.dataset.view));
  });
  navigate('overview');
});
