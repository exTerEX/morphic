/* ── Morphic — Unified JS ─────────────────────────────────────────── */

// =====================================================================
// Global state
// =====================================================================

let activeTab = 'converter';

// Converter state
let convScanData = null;        // last scan result
let convFilterType = 'both';    // images|videos|both
let convFilterExt = null;       // filter by specific extension
let convSelectedFiles = [];     // files selected for conversion
let convJobId = null;
let convPollTimer = null;
let showFullPaths = false;

// Dupfinder state
let dupJobId = null;
let dupPollTimer = null;
let dupAllGroups = [];
let dupSelectedFiles = new Set();

// Inspector state
let inspJobId = null;
let inspPollTimer = null;

// Resizer state
let resJobId = null;
let resPollTimer = null;

// Organizer state
let orgJobId = null;
let orgPollTimer = null;

// =====================================================================
// Tabs
// =====================================================================

function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === tab);
    });
    document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.toggle('active', c.id === 'tab-' + tab);
    });
}

// =====================================================================
// Shared: In-page Folder Browser
// =====================================================================

const _browserPrefixes = {
    converter: 'conv', dupfinder: 'dup',
    inspector: 'insp', resizer: 'res',
    organizer: 'org',
};

function _bp(tab) { return _browserPrefixes[tab] || tab; }

function toggleBrowser(tab) {
    const browser = document.getElementById(_bp(tab) + 'Browser');
    if (browser.classList.contains('open')) {
        browser.classList.remove('open');
    } else {
        const input = document.getElementById(_bp(tab) + 'Folder');
        browseTo(input.value.trim() || '~', tab);
    }
}

function closeBrowser(tab) {
    document.getElementById(_bp(tab) + 'Browser').classList.remove('open');
}

function selectBrowserFolder(tab) {
    closeBrowser(tab);
    showToast('Folder selected', 'success');
}

async function browseTo(path, tab) {
    try {
        const resp = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
        const data = await resp.json();
        if (data.error) { showToast(data.error, 'error'); return; }

        const prefix = _bp(tab);
        const input = document.getElementById(prefix + 'Folder');
        input.value = data.current;

        const browser = document.getElementById(prefix + 'Browser');
        const fbPath = browser.querySelector('.fb-path');
        fbPath.textContent = data.current;

        const parentEl = browser.querySelector('.fb-parent');
        if (data.parent) {
            parentEl.style.display = 'flex';
            parentEl.onclick = () => browseTo(data.parent, tab);
        } else {
            parentEl.style.display = 'none';
        }

        const entriesEl = browser.querySelector('.fb-entries');
        entriesEl.innerHTML = '';
        for (const entry of data.entries) {
            const div = document.createElement('div');
            div.className = 'fb-item';
            div.innerHTML = `<span class="icon">📁</span> ${escapeHtml(entry.name)}`;
            div.onclick = () => browseTo(entry.path, tab);
            entriesEl.appendChild(div);
        }

        browser.classList.add('open');
    } catch (e) {
        showToast('Failed to browse: ' + e.message, 'error');
    }
}

// =====================================================================
// Converter: Scan
// =====================================================================

async function convScan() {
    const folder = document.getElementById('convFolder').value.trim();
    if (!folder) { showToast('Enter a folder path', 'error'); return; }

    const includeSubfolders = document.getElementById('convSubfolders').checked;
    const filterType = document.getElementById('convFilterType').value;

    document.getElementById('convScanBtn').disabled = true;
    document.getElementById('convResults').style.display = 'none';

    try {
        const resp = await fetch('/api/converter/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder, include_subfolders: includeSubfolders, filter_type: filterType,
            }),
        });
        const data = await resp.json();
        if (data.error) { showToast(data.error, 'error'); return; }

        convScanData = data;
        convFilterType = filterType;
        convFilterExt = null;
        convSelectedFiles = [];
        renderConvResults();
    } catch (e) {
        showToast('Scan failed: ' + e.message, 'error');
    } finally {
        document.getElementById('convScanBtn').disabled = false;
    }
}

function renderConvResults() {
    if (!convScanData) return;
    const section = document.getElementById('convResults');
    section.style.display = 'block';

    // Summary
    const summary = document.getElementById('convSummary');
    const entries = Object.entries(convScanData.summary);
    if (entries.length === 0) {
        summary.innerHTML = '<div class="empty-state"><div class="icon">📂</div><h3>No media files found</h3></div>';
        document.getElementById('convFileTable').innerHTML = '';
        return;
    }

    let html = `<strong>${convScanData.total}</strong> files found in <code>${escapeHtml(convScanData.folder)}</code>`;
    html += '<div class="filter-pills">';
    html += `<span class="filter-pill ${!convFilterExt ? 'active' : ''}" onclick="convSetExtFilter(null)">All</span>`;
    for (const [ext, count] of entries) {
        const isActive = convFilterExt === ext;
        html += `<span class="filter-pill ${isActive ? 'active' : ''}" onclick="convSetExtFilter('${ext}')">${ext} (${count})</span>`;
    }
    html += '</div>';
    summary.innerHTML = html;

    // File table
    let files = convScanData.files;
    if (convFilterExt) {
        files = files.filter(f => f.ext === convFilterExt);
    }

    const table = document.getElementById('convFileTable');
    if (files.length === 0) {
        table.innerHTML = '<p style="color:var(--text-dim);padding:20px;">No files match current filter.</p>';
        return;
    }

    let thtml = `<table class="file-table">
        <thead><tr>
            <th style="width:50px"></th>
            <th><label class="checkbox-label"><input type="checkbox" id="convSelectAll" onchange="convToggleAll(this.checked)"> File</label></th>
            <th>Type</th>
            <th>Size</th>
            <th>Convert to</th>
            <th></th>
        </tr></thead><tbody>`;

    for (const f of files) {
        const thumbUrl = `/api/thumbnail?path=${encodeURIComponent(f.path)}`;
        const displayName = showFullPaths ? f.path : f.name;

        thtml += `<tr data-path="${escapeAttr(f.path)}">
            <td><img src="${thumbUrl}" class="file-thumb" onclick="openPreview('${escapeAttr(f.path)}', '${f.type}')" onerror="this.style.display='none'" /></td>
            <td>
                <label class="checkbox-label">
                    <input type="checkbox" class="conv-check" value="${escapeAttr(f.path)}" onchange="convUpdateSelection()">
                    <span class="file-name" title="${escapeAttr(f.path)}" onclick="copyPath('${escapeAttr(f.path)}')">${escapeHtml(displayName)}</span>
                </label>
            </td>
            <td>${f.ext}</td>
            <td>${formatBytes(f.size)}</td>
            <td>
                <select class="conv-target" style="font-size:12px;padding:4px 8px;background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:4px;">
                    ${f.targets.map(t => `<option value="${t}">${t}</option>`).join('')}
                </select>
            </td>
            <td>
                <button class="btn btn-sm btn-ghost" onclick="convConvertSingle('${escapeAttr(f.path)}', this)">Convert</button>
                <button class="btn btn-sm btn-ghost" style="color:var(--danger)" onclick="convDeleteSingle('${escapeAttr(f.path)}')">✕</button>
            </td>
        </tr>`;
    }

    thtml += '</tbody></table>';
    table.innerHTML = thtml;
}

function convSetExtFilter(ext) {
    convFilterExt = ext;
    renderConvResults();
}

function convToggleAll(checked) {
    document.querySelectorAll('.conv-check').forEach(cb => cb.checked = checked);
    convUpdateSelection();
}

function convUpdateSelection() {
    convSelectedFiles = [];
    document.querySelectorAll('.conv-check:checked').forEach(cb => {
        convSelectedFiles.push(cb.value);
    });

    const bar = document.getElementById('convBulkBar');
    if (convSelectedFiles.length > 0) {
        bar.style.display = 'flex';
        document.getElementById('convBulkCount').textContent = convSelectedFiles.length;
    } else {
        bar.style.display = 'none';
    }
}

function toggleFullPaths() {
    showFullPaths = !showFullPaths;
    renderConvResults();
}

// =====================================================================
// Converter: Convert
// =====================================================================

async function convConvertSingle(filePath, btnEl) {
    const row = btnEl.closest('tr');
    const targetSelect = row.querySelector('.conv-target');
    const targetExt = targetSelect.value;
    const deleteOrig = document.getElementById('convDeleteOrig').checked;

    btnEl.disabled = true;
    btnEl.textContent = '...';

    try {
        const resp = await fetch('/api/converter/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: [filePath],
                target_ext: targetExt,
                delete_original: deleteOrig,
            }),
        });
        const data = await resp.json();
        if (data.job_id) {
            await convWaitForJob(data.job_id);
        }
    } catch (e) {
        showToast('Convert failed: ' + e.message, 'error');
    } finally {
        btnEl.disabled = false;
        btnEl.textContent = 'Convert';
    }
}

async function convConvertBatch() {
    if (convSelectedFiles.length === 0) return;
    const targetExt = document.getElementById('convBatchTarget').value;
    const deleteOrig = document.getElementById('convDeleteOrig').checked;

    document.getElementById('convBatchBtn').disabled = true;

    try {
        const resp = await fetch('/api/converter/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: convSelectedFiles,
                target_ext: targetExt,
                delete_original: deleteOrig,
            }),
        });
        const data = await resp.json();
        if (data.job_id) {
            convShowProgress();
            convPollProgress(data.job_id);
        }
    } catch (e) {
        showToast('Batch convert failed: ' + e.message, 'error');
        document.getElementById('convBatchBtn').disabled = false;
    }
}

function convShowProgress() {
    document.getElementById('convProgress').classList.add('active');
}

function convPollProgress(jobId) {
    let lastCompleted = -1;
    convPollTimer = setInterval(async () => {
        try {
            const resp = await fetch(`/api/converter/progress/${jobId}/poll?last=${lastCompleted}`);
            const data = await resp.json();
            if (data.error) return;

            lastCompleted = data.completed;
            const pct = data.total > 0 ? Math.round((data.completed / data.total) * 100) : 0;
            document.getElementById('convProgressBar').style.width = pct + '%';
            document.getElementById('convProgressPct').textContent = pct + '%';
            document.getElementById('convProgressMsg').textContent =
                data.current_file ? `Converting: ${data.current_file}` : 'Processing...';

            if (data.status === 'done') {
                clearInterval(convPollTimer);
                convShowConversionResults(data);
                document.getElementById('convProgress').classList.remove('active');
                document.getElementById('convBatchBtn').disabled = false;
            }
        } catch (e) { /* retry */ }
    }, 500);
}

async function convWaitForJob(jobId) {
    // Simple wait for single-file conversions
    while (true) {
        const resp = await fetch(`/api/converter/progress/${jobId}`);
        const data = await resp.json();
        if (data.status === 'done') {
            const r = data.results[0];
            if (r.status === 'ok') {
                const sizeInfo = r.original_size_fmt + ' → ' + r.new_size_fmt;
                showToast(`Converted! (${sizeInfo})`, 'success');
            } else {
                showToast('Error: ' + (r.error || 'unknown'), 'error');
            }
            return;
        }
        await sleep(300);
    }
}

function convShowConversionResults(data) {
    let ok = 0, fail = 0;
    for (const r of data.results) {
        if (r.status === 'ok') ok++;
        else fail++;
    }
    showToast(`Done! ${ok} converted, ${fail} failed`, ok > 0 ? 'success' : 'error');
    // Re-scan to update file list
    convScan();
}

async function convDeleteSingle(filePath) {
    if (!confirm('Delete this file permanently?')) return;
    try {
        const resp = await fetch('/api/converter/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filePath] }),
        });
        const data = await resp.json();
        const r = data.results[0];
        if (r.status === 'deleted') {
            showToast('Deleted', 'success');
            // Remove from scan data
            if (convScanData) {
                convScanData.files = convScanData.files.filter(f => f.path !== filePath);
                convScanData.total = convScanData.files.length;
            }
            renderConvResults();
        } else {
            showToast('Delete failed: ' + (r.status), 'error');
        }
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

async function convDeleteBatch() {
    if (convSelectedFiles.length === 0) return;
    if (!confirm(`Permanently delete ${convSelectedFiles.length} file(s)?`)) return;
    try {
        const resp = await fetch('/api/converter/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: convSelectedFiles }),
        });
        const data = await resp.json();
        const deleted = data.results.filter(r => r.status === 'deleted');
        const failed = data.results.filter(r => r.status !== 'deleted');

        if (deleted.length > 0) {
            showToast(`Deleted ${deleted.length} file(s), freed ${data.total_freed_formatted}`, 'success');
            if (convScanData) {
                const deletedPaths = new Set(deleted.map(r => r.path));
                convScanData.files = convScanData.files.filter(f => !deletedPaths.has(f.path));
                convScanData.total = convScanData.files.length;
                // Recalculate summary
                const newSummary = {};
                for (const f of convScanData.files) {
                    newSummary[f.ext] = (newSummary[f.ext] || 0) + 1;
                }
                convScanData.summary = newSummary;
            }
        }
        if (failed.length > 0) {
            showToast(`Failed to delete ${failed.length} file(s)`, 'error');
        }

        convSelectedFiles = [];
        renderConvResults();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

function copyPath(path) {
    navigator.clipboard.writeText(path).then(() => {
        showToast('Path copied', 'success');
    });
}

// =====================================================================
// Dupfinder: Scan
// =====================================================================

async function dupStartScan() {
    const folder = document.getElementById('dupFolder').value.trim();
    if (!folder) { showToast('Enter a folder path', 'error'); return; }

    const scanType = document.getElementById('dupScanType').value;
    const imgThreshold = parseInt(document.getElementById('dupImgThreshold').value) / 100;
    const vidThreshold = parseInt(document.getElementById('dupVidThreshold').value) / 100;

    document.getElementById('dupScanBtn').disabled = true;
    document.getElementById('dupResults').classList.remove('active');
    document.getElementById('dupProgress').classList.add('active');
    document.getElementById('dupProgressBar').style.width = '0%';
    document.getElementById('dupProgressPct').textContent = '0%';
    document.getElementById('dupProgressMsg').textContent = 'Starting scan...';

    try {
        const resp = await fetch('/api/dupfinder/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder, type: scanType,
                image_threshold: imgThreshold,
                video_threshold: vidThreshold,
            }),
        });
        const data = await resp.json();
        if (data.error) {
            showToast(data.error, 'error');
            dupResetUI();
            return;
        }
        dupJobId = data.job_id;
        dupPollProgress();
    } catch (e) {
        showToast('Scan failed: ' + e.message, 'error');
        dupResetUI();
    }
}

function dupPollProgress() {
    if (!dupJobId) return;
    dupPollTimer = setInterval(async () => {
        try {
            const resp = await fetch(`/api/dupfinder/scan/${dupJobId}/status`);
            const data = await resp.json();

            const pct = Math.round(data.progress * 100);
            document.getElementById('dupProgressBar').style.width = pct + '%';
            document.getElementById('dupProgressPct').textContent = pct + '%';
            document.getElementById('dupProgressMsg').textContent = data.message || '';
            document.getElementById('dupProgressElapsed').textContent = formatDuration(data.elapsed_seconds || 0);

            if (data.status === 'done') {
                clearInterval(dupPollTimer);
                await dupLoadResults();
            } else if (data.status === 'error') {
                clearInterval(dupPollTimer);
                showToast('Scan failed: ' + (data.error || 'Unknown'), 'error');
                dupResetUI();
            }
        } catch (e) { /* retry */ }
    }, 500);
}

async function dupLoadResults() {
    try {
        const resp = await fetch(`/api/dupfinder/scan/${dupJobId}/results`);
        const data = await resp.json();

        dupAllGroups = [];
        let idx = 0;
        for (const g of (data.image_groups || [])) dupAllGroups.push({ index: idx++, type: 'image', items: g });
        for (const g of (data.video_groups || [])) dupAllGroups.push({ index: idx++, type: 'video', items: g });

        dupRenderResults(data);
        document.getElementById('dupProgress').classList.remove('active');
        document.getElementById('dupResults').classList.add('active');
        dupResetUI();

        document.getElementById('dupNoResults').style.display =
            dupAllGroups.length === 0 ? 'block' : 'none';
    } catch (e) {
        showToast('Failed to load results', 'error');
        dupResetUI();
    }
}

function dupResetUI() {
    document.getElementById('dupScanBtn').disabled = false;
}

// =====================================================================
// Dupfinder: Render
// =====================================================================

function dupRenderResults(data) {
    const totalGroups = dupAllGroups.length;
    const totalDups = dupAllGroups.reduce((s, g) => s + g.items.length - 1, 0);

    document.getElementById('dupSummary').innerHTML = `
        <div class="stat-card"><div class="stat-value">${totalGroups}</div><div class="stat-label">Duplicate Groups</div></div>
        <div class="stat-card"><div class="stat-value">${totalDups}</div><div class="stat-label">Duplicate Files</div></div>
        <div class="stat-card savings"><div class="stat-value">${data.space_savings_formatted}</div><div class="stat-label">Potential Savings</div></div>
    `;

    document.getElementById('dupTitle').textContent =
        `${totalGroups} Duplicate Group${totalGroups !== 1 ? 's' : ''} Found`;

    const container = document.getElementById('dupGroups');
    container.innerHTML = '';
    for (const group of dupAllGroups) {
        container.appendChild(dupCreateGroupCard(group));
    }
}

function dupCreateGroupCard(group) {
    const div = document.createElement('div');
    div.className = 'group-card';
    div.dataset.groupIndex = group.index;

    const typeLabel = group.type === 'image' ? 'Image' : 'Video';
    const badgeClass = group.type === 'video' ? 'group-badge video' : 'group-badge';

    div.innerHTML = `
        <div class="group-header" onclick="dupToggleGroup(${group.index})">
            <div class="group-title">
                <span class="${badgeClass}">${typeLabel}</span>
                Group ${group.index + 1} — ${group.items.length} files
            </div>
            <span class="toggle-icon">▼</span>
        </div>
        <div class="group-body" id="dupGroupBody${group.index}">
            <div class="dup-grid">
                ${group.items.map((item, i) => dupCreateFileCard(item, i === 0, group.index)).join('')}
            </div>
        </div>
    `;
    return div;
}

function dupCreateFileCard(item, isBest) {
    const isSelected = dupSelectedFiles.has(item.path);
    const selClass = isSelected ? 'selected-for-delete' : (isBest ? 'is-best' : '');

    let thumb;
    if (item.type === 'video') {
        thumb = `<video src="/api/media?path=${encodeURIComponent(item.path)}" muted preload="metadata"></video>`;
    } else {
        thumb = `<img src="/api/thumbnail?path=${encodeURIComponent(item.path)}" alt="${escapeAttr(item.filename)}" loading="lazy" />`;
    }

    const badges = [];
    if (isBest) badges.push(`<span class="best-badge">★ BEST</span>`);
    badges.push(`<span class="sim-badge">${item.similarity}%</span>`);

    const meta = [];
    meta.push(item.resolution);
    meta.push(item.file_size_formatted);
    if (item.duration_formatted) meta.push(item.duration_formatted);
    if (item.format) meta.push(item.format);

    return `
        <div class="file-card ${selClass}" data-path="${escapeAttr(item.path)}" data-size="${item.file_size}">
            <div class="thumb-container" onclick="openPreview('${escapeAttr(item.path)}', '${item.type}')">
                ${thumb}
                <div class="badge-row">${badges.join('')}</div>
                <div class="thumb-overlay">Click to preview</div>
            </div>
            <div class="file-info">
                <div class="file-name" title="${escapeAttr(item.path)}">${escapeHtml(item.filename)}</div>
                <div class="file-dir" title="${escapeAttr(item.directory)}">${escapeHtml(item.directory)}</div>
                <div class="file-meta">${meta.join(' · ')}</div>
            </div>
            <div class="file-actions">
                ${isBest
                    ? `<button class="btn ${isSelected ? 'btn-ghost' : 'btn-ghost'} btn-sm" style="flex:1;border-color:${isSelected ? 'var(--danger)' : 'var(--success)'}"
                         onclick="dupToggleFile('${escapeAttr(item.path)}')">
                         ${isSelected ? '↩ Unselect (★ best)' : '★ Recommended to keep'}
                       </button>`
                    : `<button class="btn ${isSelected ? 'btn-ghost' : 'btn-danger'} btn-sm" style="flex:1"
                         onclick="dupToggleFile('${escapeAttr(item.path)}')">
                         ${isSelected ? '↩ Unselect' : '🗑 Select to delete'}
                       </button>`
                }
            </div>
        </div>
    `;
}

// =====================================================================
// Dupfinder: Selection & Deletion
// =====================================================================

function dupToggleGroup(index) {
    const body = document.getElementById(`dupGroupBody${index}`);
    body.classList.toggle('collapsed');
    const icon = body.closest('.group-card').querySelector('.toggle-icon');
    icon.textContent = body.classList.contains('collapsed') ? '▶' : '▼';
}

function dupExpandAll() {
    document.querySelectorAll('#dupGroups .group-body').forEach(b => b.classList.remove('collapsed'));
    document.querySelectorAll('#dupGroups .toggle-icon').forEach(i => i.textContent = '▼');
}

function dupCollapseAll() {
    document.querySelectorAll('#dupGroups .group-body').forEach(b => b.classList.add('collapsed'));
    document.querySelectorAll('#dupGroups .toggle-icon').forEach(i => i.textContent = '▶');
}

function dupToggleFile(path) {
    if (dupSelectedFiles.has(path)) dupSelectedFiles.delete(path);
    else dupSelectedFiles.add(path);
    dupUpdateSelectionUI();
}

function dupAutoSelect() {
    dupSelectedFiles.clear();
    for (const g of dupAllGroups) {
        for (let i = 1; i < g.items.length; i++) {
            dupSelectedFiles.add(g.items[i].path);
        }
    }
    dupUpdateSelectionUI();
    showToast(`Selected ${dupSelectedFiles.size} duplicate(s)`, 'success');
}

function dupClearSelection() {
    dupSelectedFiles.clear();
    dupUpdateSelectionUI();
}

function dupUpdateSelectionUI() {
    document.querySelectorAll('#dupGroups .file-card').forEach(card => {
        const path = card.dataset.path;
        const isSelected = dupSelectedFiles.has(path);
        card.classList.toggle('selected-for-delete', isSelected);
        card.classList.toggle('is-best', !isSelected && !!card.querySelector('.best-badge'));

        const btn = card.querySelector('.file-actions button');
        if (btn) {
            const hasBest = !!card.querySelector('.best-badge');
            if (isSelected) {
                btn.className = 'btn btn-ghost btn-sm';
                btn.style.flex = '1';
                btn.style.borderColor = hasBest ? 'var(--danger)' : '';
                btn.innerHTML = hasBest ? '↩ Unselect (★ best)' : '↩ Unselect';
            } else if (hasBest) {
                btn.className = 'btn btn-ghost btn-sm';
                btn.style.flex = '1';
                btn.style.borderColor = 'var(--success)';
                btn.innerHTML = '★ Recommended to keep';
            } else {
                btn.className = 'btn btn-danger btn-sm';
                btn.style.flex = '1';
                btn.style.borderColor = '';
                btn.innerHTML = '🗑 Select to delete';
            }
        }
    });

    const bulkBar = document.getElementById('dupBulkBar');
    if (dupSelectedFiles.size > 0) {
        bulkBar.classList.add('active');
        document.getElementById('dupBulkCount').textContent = dupSelectedFiles.size;
        let totalSize = 0;
        document.querySelectorAll('#dupGroups .file-card').forEach(card => {
            if (dupSelectedFiles.has(card.dataset.path)) {
                totalSize += parseInt(card.dataset.size) || 0;
            }
        });
        document.getElementById('dupBulkSize').textContent = formatBytes(totalSize);
    } else {
        bulkBar.classList.remove('active');
    }
}

function dupConfirmDelete() {
    if (dupSelectedFiles.size === 0) return;
    const fileList = document.getElementById('dupDeleteFileList');
    fileList.innerHTML = '';
    for (const path of dupSelectedFiles) {
        const div = document.createElement('div');
        div.textContent = path;
        fileList.appendChild(div);
    }
    document.getElementById('dupDeleteModal').classList.add('active');
}

function dupCloseModal() {
    document.getElementById('dupDeleteModal').classList.remove('active');
}

async function dupExecuteDelete() {
    const files = Array.from(dupSelectedFiles);
    const btn = document.getElementById('dupConfirmDeleteBtn');
    btn.disabled = true;
    btn.textContent = 'Deleting...';

    try {
        const resp = await fetch('/api/dupfinder/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files }),
        });
        const data = await resp.json();
        const deleted = data.results.filter(r => r.status === 'deleted');
        const failed = data.results.filter(r => r.status !== 'deleted');

        if (deleted.length > 0) showToast(`Deleted ${deleted.length} file(s), freed ${data.total_freed_formatted}`, 'success');
        if (failed.length > 0) showToast(`Failed to delete ${failed.length} file(s)`, 'error');

        for (const r of deleted) {
            dupSelectedFiles.delete(r.path);
            const card = document.querySelector(`#dupGroups .file-card[data-path="${CSS.escape(r.path)}"]`);
            if (card) card.remove();
            for (const g of dupAllGroups) {
                g.items = g.items.filter(item => item.path !== r.path);
            }
        }

        dupAllGroups = dupAllGroups.filter(g => g.items.length > 1);
        const container = document.getElementById('dupGroups');
        container.innerHTML = '';
        for (const g of dupAllGroups) container.appendChild(dupCreateGroupCard(g));
        dupUpdateSelectionUI();

        if (dupAllGroups.length === 0) {
            document.getElementById('dupNoResults').style.display = 'block';
            document.getElementById('dupTitle').textContent = 'All duplicates resolved!';
            document.getElementById('dupSummary').innerHTML = '';
        }
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    } finally {
        dupCloseModal();
        btn.disabled = false;
        btn.textContent = '🗑️ Delete';
    }
}

// =====================================================================
// Inspector Tab
// =====================================================================

async function inspStartScan() {
    const folder = document.getElementById('inspFolder').value.trim();
    if (!folder) { showToast('Enter a folder path', 'error'); return; }
    const mode = document.getElementById('inspMode').value;

    document.getElementById('inspScanBtn').disabled = true;
    document.getElementById('inspResults').style.display = 'none';
    document.getElementById('inspProgress').style.display = 'block';
    document.getElementById('inspProgressBar').style.width = '0%';
    document.getElementById('inspProgressPct').textContent = '0%';
    document.getElementById('inspProgressMsg').textContent = 'Starting...';

    try {
        const resp = await fetch('/api/inspector/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder, mode }),
        });
        const data = await resp.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        inspJobId = data.job_id;
        inspPollTimer = setInterval(inspPollProgress, 800);
    } catch (e) {
        showToast('Scan failed: ' + e.message, 'error');
        document.getElementById('inspProgress').style.display = 'none';
    } finally {
        document.getElementById('inspScanBtn').disabled = false;
    }
}

async function inspPollProgress() {
    try {
        const resp = await fetch(`/api/inspector/scan/${inspJobId}/status`);
        const data = await resp.json();
        const total = data.total_files || 0;
        const processed = data.processed_files || 0;
        const pct = total > 0 ? Math.round((processed / total) * 100) : 0;
        document.getElementById('inspProgressBar').style.width = pct + '%';
        document.getElementById('inspProgressPct').textContent = pct + '%';
        document.getElementById('inspProgressMsg').textContent = `${processed} / ${total} files`;

        if (data.status === 'done' || data.status === 'error') {
            clearInterval(inspPollTimer);
            document.getElementById('inspProgress').style.display = 'none';
            if (data.status === 'error') {
                showToast('Scan error: ' + (data.error || 'Unknown'), 'error');
            } else {
                inspLoadResults();
            }
        }
    } catch (e) {
        clearInterval(inspPollTimer);
        showToast('Poll error: ' + e.message, 'error');
    }
}

async function inspLoadResults() {
    try {
        const resp = await fetch(`/api/inspector/scan/${inspJobId}/results`);
        const data = await resp.json();
        const container = document.getElementById('inspResultsContent');
        const section = document.getElementById('inspResults');
        section.style.display = 'block';

        if (!data.results || data.results.length === 0) {
            container.innerHTML = '<div class="card"><div class="empty-state"><div class="icon">📂</div><h3>No files found</h3></div></div>';
            return;
        }

        const mode = document.getElementById('inspMode').value;
        if (mode === 'exif') {
            inspRenderExif(data.results, container);
        } else {
            inspRenderIntegrity(data.results, container);
        }
    } catch (e) {
        showToast('Failed to load results: ' + e.message, 'error');
    }
}

function inspRenderExif(results, container) {
    let html = `<div class="card"><div class="card-title"><span class="icon">📊</span> EXIF Results — ${results.length} file(s)</div></div>`;
    for (const item of results) {
        const fname = item.file.split('/').pop();
        const exif = item.exif || {};
        const keys = Object.keys(exif).filter(k => !k.startsWith('_'));
        html += `<div class="card exif-card">
            <div class="card-title" style="font-size:14px;cursor:pointer;" onclick="this.parentElement.classList.toggle('expanded')">
                📄 ${escapeHtml(fname)} <span style="color:var(--text-dim);font-weight:normal;margin-left:8px;">${keys.length} tags</span>
            </div>
            <div class="exif-details">
                <div style="display:flex;gap:8px;margin-bottom:10px;">
                    <button class="btn btn-ghost btn-sm" onclick="inspStripOne('${escapeAttr(item.file)}')">🧹 Strip EXIF</button>
                </div>
                <table class="exif-table"><tbody>`;
        for (const k of keys) {
            const val = typeof exif[k] === 'object' ? JSON.stringify(exif[k]) : String(exif[k]);
            html += `<tr><td class="exif-key">${escapeHtml(k)}</td><td>${escapeHtml(val.substring(0, 200))}</td></tr>`;
        }
        if (exif._gps_lat && exif._gps_lng) {
            html += `<tr><td class="exif-key">📍 GPS</td><td>${exif._gps_lat.toFixed(6)}, ${exif._gps_lng.toFixed(6)}</td></tr>`;
        }
        html += `</tbody></table></div></div>`;
    }
    container.innerHTML = html;
}

function inspRenderIntegrity(results, container) {
    let ok = 0, bad = 0;
    for (const r of results) { if (r.ok) ok++; else bad++; }

    let html = `<div class="card">
        <div class="card-title"><span class="icon">📊</span> Integrity Results</div>
        <div class="stat-row">
            <div class="stat-card"><div class="stat-value" style="color:var(--success)">${ok}</div><div class="stat-label">OK</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--danger)">${bad}</div><div class="stat-label">Errors</div></div>
            <div class="stat-card"><div class="stat-value">${results.length}</div><div class="stat-label">Total</div></div>
        </div></div>`;

    if (bad > 0) {
        html += '<div class="card"><div class="card-title" style="color:var(--danger)">⚠️ Failed Files</div>';
        for (const r of results.filter(x => !x.ok)) {
            html += `<div class="integrity-item bad"><span class="file-name">${escapeHtml(r.file.split('/').pop())}</span><span class="integrity-error">${escapeHtml(r.error || 'Unknown error')}</span></div>`;
        }
        html += '</div>';
    }
    container.innerHTML = html;
}

async function inspStripOne(filePath) {
    try {
        const resp = await fetch('/api/inspector/exif/strip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filePath] }),
        });
        const data = await resp.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        showToast('EXIF stripped from 1 file', 'success');
    } catch (e) {
        showToast('Strip failed: ' + e.message, 'error');
    }
}

// =====================================================================
// Resizer Tab
// =====================================================================

async function resStartResize() {
    const folder = document.getElementById('resFolder').value.trim();
    if (!folder) { showToast('Enter a folder path', 'error'); return; }

    const width = parseInt(document.getElementById('resWidth').value) || 1920;
    const height = parseInt(document.getElementById('resHeight').value) || 1080;
    const mode = document.getElementById('resMode').value;
    const quality = parseInt(document.getElementById('resQuality').value) || 90;
    const bgColor = document.getElementById('resBgColor').value;
    const outputFolder = document.getElementById('resOutput').value.trim() || null;

    document.getElementById('resScanBtn').disabled = true;
    document.getElementById('resResults').style.display = 'none';
    document.getElementById('resProgress').style.display = 'block';
    document.getElementById('resProgressBar').style.width = '0%';
    document.getElementById('resProgressPct').textContent = '0%';
    document.getElementById('resProgressMsg').textContent = 'Starting...';

    try {
        const resp = await fetch('/api/resizer/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder, width, height, mode, quality, bg_color: bgColor, output_folder: outputFolder }),
        });
        const data = await resp.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        resJobId = data.job_id;
        resPollTimer = setInterval(resPollProgress, 800);
    } catch (e) {
        showToast('Resize failed: ' + e.message, 'error');
        document.getElementById('resProgress').style.display = 'none';
    } finally {
        document.getElementById('resScanBtn').disabled = false;
    }
}

async function resPollProgress() {
    try {
        const resp = await fetch(`/api/resizer/scan/${resJobId}/status`);
        const data = await resp.json();
        const total = data.total_files || 0;
        const processed = data.processed_files || 0;
        const pct = total > 0 ? Math.round((processed / total) * 100) : 0;
        document.getElementById('resProgressBar').style.width = pct + '%';
        document.getElementById('resProgressPct').textContent = pct + '%';
        document.getElementById('resProgressMsg').textContent = `${processed} / ${total} images`;

        if (data.status === 'done' || data.status === 'error') {
            clearInterval(resPollTimer);
            document.getElementById('resProgress').style.display = 'none';
            if (data.status === 'error') {
                showToast('Resize error: ' + (data.error || 'Unknown'), 'error');
            } else {
                resLoadResults();
            }
        }
    } catch (e) {
        clearInterval(resPollTimer);
        showToast('Poll error: ' + e.message, 'error');
    }
}

async function resLoadResults() {
    try {
        const resp = await fetch(`/api/resizer/scan/${resJobId}/results`);
        const data = await resp.json();
        const container = document.getElementById('resResultsContent');
        const section = document.getElementById('resResults');
        section.style.display = 'block';

        const results = data.results || [];
        let ok = 0, errors = 0;
        for (const r of results) { if (r.status === 'ok') ok++; else errors++; }

        let html = `<div class="card">
            <div class="card-title"><span class="icon">📊</span> Resize Results</div>
            <div class="stat-row">
                <div class="stat-card"><div class="stat-value" style="color:var(--success)">${ok}</div><div class="stat-label">Resized</div></div>
                <div class="stat-card"><div class="stat-value" style="color:var(--danger)">${errors}</div><div class="stat-label">Errors</div></div>
                <div class="stat-card"><div class="stat-value">${results.length}</div><div class="stat-label">Total</div></div>
            </div></div>`;

        if (errors > 0) {
            html += '<div class="card"><div class="card-title" style="color:var(--danger)">⚠️ Errors</div>';
            for (const r of results.filter(x => x.status !== 'ok')) {
                html += `<div class="integrity-item bad"><span class="file-name">${escapeHtml(r.input.split('/').pop())}</span><span class="integrity-error">${escapeHtml(r.error || 'Unknown')}</span></div>`;
            }
            html += '</div>';
        }
        container.innerHTML = html;
    } catch (e) {
        showToast('Failed to load results: ' + e.message, 'error');
    }
}

// =====================================================================
// Organizer Tab
// =====================================================================

function orgModeChanged() {
    const mode = document.getElementById('orgMode').value;
    document.getElementById('orgSortOptions').style.display = mode === 'sort' ? 'block' : 'none';
    document.getElementById('orgRenameOptions').style.display = mode === 'rename' ? 'block' : 'none';
    document.getElementById('orgExecBtn').style.display = 'none';
    document.getElementById('orgPlanResults').style.display = 'none';
    document.getElementById('orgExecResults').style.display = 'none';
}

async function orgStartPlan() {
    const folder = document.getElementById('orgFolder').value.trim();
    if (!folder) { showToast('Enter a folder path', 'error'); return; }

    const mode = document.getElementById('orgMode').value;
    const operation = document.getElementById('orgOperation').value;

    let body = { folder, mode, operation };
    if (mode === 'sort') {
        body.template = document.getElementById('orgTemplate').value.trim() || '{year}/{month}';
        body.destination = document.getElementById('orgDest').value.trim() || null;
    } else {
        body.template = document.getElementById('orgRenameTemplate').value.trim() || '{date}_{seq:4}';
        body.start_seq = parseInt(document.getElementById('orgStartSeq').value) || 1;
    }

    document.getElementById('orgPlanBtn').disabled = true;
    document.getElementById('orgExecBtn').style.display = 'none';
    document.getElementById('orgPlanResults').style.display = 'none';
    document.getElementById('orgExecResults').style.display = 'none';
    document.getElementById('orgProgress').style.display = 'block';
    document.getElementById('orgProgressBar').style.width = '0%';
    document.getElementById('orgProgressMsg').textContent = 'Planning...';

    try {
        const resp = await fetch('/api/organizer/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        orgJobId = data.job_id;
        orgPollTimer = setInterval(orgPollStatus, 600);
    } catch (e) {
        showToast('Plan failed: ' + e.message, 'error');
        document.getElementById('orgProgress').style.display = 'none';
    } finally {
        document.getElementById('orgPlanBtn').disabled = false;
    }
}

async function orgPollStatus() {
    try {
        const resp = await fetch(`/api/organizer/status/${orgJobId}`);
        const data = await resp.json();

        const pct = Math.round((data.progress || 0) * 100);
        document.getElementById('orgProgressBar').style.width = pct + '%';
        document.getElementById('orgProgressPct').textContent = pct + '%';

        if (data.phase === 'planned') {
            clearInterval(orgPollTimer);
            document.getElementById('orgProgress').style.display = 'none';
            orgRenderPlan(data);
        } else if (data.phase === 'done') {
            clearInterval(orgPollTimer);
            document.getElementById('orgProgress').style.display = 'none';
            orgRenderExecResults(data);
        } else if (data.phase === 'error' || data.status === 'error') {
            clearInterval(orgPollTimer);
            document.getElementById('orgProgress').style.display = 'none';
            showToast('Error: ' + (data.error || 'Unknown'), 'error');
        } else {
            document.getElementById('orgProgressMsg').textContent =
                data.phase === 'executing' ? `Executing...` : `Planning...`;
        }
    } catch (e) {
        clearInterval(orgPollTimer);
        showToast('Poll error: ' + e.message, 'error');
    }
}

function orgRenderPlan(data) {
    const content = document.getElementById('orgPlanContent');
    const plan = data.plan || [];
    const conflicts = data.conflicts || 0;
    const planCount = data.plan_count || plan.length;

    let html = `<div class="card-title"><span class="icon">📋</span> Plan Preview — ${planCount} file(s)</div>`;
    if (conflicts > 0) {
        html += `<div class="toast error" style="position:static;margin-bottom:12px;">⚠️ ${conflicts} conflict(s) detected — those will be skipped.</div>`;
    }

    html += '<div style="max-height:400px;overflow:auto;"><table class="exif-table"><thead><tr><th>Source</th><th>→</th><th>Destination</th></tr></thead><tbody>';
    for (const item of plan.slice(0, 200)) {
        const srcName = item.source.split('/').pop();
        const dstName = item.destination.split('/').pop();
        const conflict = item.conflict ? ' style="color:var(--danger);"' : '';
        html += `<tr${conflict}><td title="${escapeAttr(item.source)}">${escapeHtml(srcName)}</td><td>→</td><td title="${escapeAttr(item.destination)}">${escapeHtml(dstName)}</td></tr>`;
    }
    if (plan.length > 200) html += `<tr><td colspan="3" style="color:var(--text-dim);">… and ${plan.length - 200} more</td></tr>`;
    html += '</tbody></table></div>';

    content.innerHTML = html;
    document.getElementById('orgPlanResults').style.display = 'block';
    document.getElementById('orgExecBtn').style.display = 'inline-flex';
}

async function orgExecute() {
    if (!orgJobId) { showToast('No plan to execute', 'error'); return; }

    document.getElementById('orgExecBtn').disabled = true;
    document.getElementById('orgProgress').style.display = 'block';
    document.getElementById('orgProgressMsg').textContent = 'Executing...';
    document.getElementById('orgProgressBar').style.width = '0%';

    try {
        const resp = await fetch('/api/organizer/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: orgJobId }),
        });
        const data = await resp.json();
        if (data.error) { showToast(data.error, 'error'); return; }
        orgPollTimer = setInterval(orgPollStatus, 600);
    } catch (e) {
        showToast('Execute failed: ' + e.message, 'error');
        document.getElementById('orgProgress').style.display = 'none';
    } finally {
        document.getElementById('orgExecBtn').disabled = false;
    }
}

function orgRenderExecResults(data) {
    const container = document.getElementById('orgExecContent');
    const r = data.execution || {};
    const completed = r.completed || 0;
    const errList = r.errors || [];
    const errors = typeof errList === 'number' ? errList : errList.length;
    const skipped = r.skipped || 0;

    let html = `<div class="card">
        <div class="card-title"><span class="icon">✅</span> Execution Complete</div>
        <div class="stat-row">
            <div class="stat-card"><div class="stat-value" style="color:var(--success)">${completed}</div><div class="stat-label">Processed</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--warning)">${skipped}</div><div class="stat-label">Skipped</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--danger)">${errors}</div><div class="stat-label">Errors</div></div>
        </div></div>`;

    if (errors > 0) {
        html += '<div class="card"><div class="card-title" style="color:var(--danger)">⚠️ Errors</div>';
        for (const e of (r.errors || [])) {
            html += `<div class="integrity-item bad"><span class="file-name">${escapeHtml(e.file || 'unknown')}</span><span class="integrity-error">${escapeHtml(e.error || '')}</span></div>`;
        }
        html += '</div>';
    }

    container.innerHTML = html;
    document.getElementById('orgExecResults').style.display = 'block';
    document.getElementById('orgPlanResults').style.display = 'none';
    document.getElementById('orgExecBtn').style.display = 'none';
    showToast(`Done: ${completed} file(s) processed`, 'success');
}

// =====================================================================
// Shared: Preview
// =====================================================================

function openPreview(path, type) {
    const content = document.getElementById('previewContent');
    if (type === 'video') {
        content.innerHTML = `<video src="/api/media?path=${encodeURIComponent(path)}" controls autoplay style="max-width:90vw;max-height:90vh;border-radius:8px;" onclick="event.stopPropagation()"></video>`;
    } else {
        content.innerHTML = `<img src="/api/media?path=${encodeURIComponent(path)}" style="max-width:90vw;max-height:90vh;border-radius:8px;" onclick="event.stopPropagation()" />`;
    }
    document.getElementById('previewOverlay').classList.add('active');
}

function closePreview() {
    const overlay = document.getElementById('previewOverlay');
    overlay.classList.remove('active');
    const video = overlay.querySelector('video');
    if (video) video.pause();
    document.getElementById('previewContent').innerHTML = '';
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closePreview(); dupCloseModal(); }
});

// =====================================================================
// Utilities
// =====================================================================

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + units[i];
}

function formatDuration(seconds) {
    if (seconds < 60) return Math.round(seconds) + 's';
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
