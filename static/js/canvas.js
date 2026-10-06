function openCanvasModal() {
  document.getElementById('settingsDropdown').style.display = 'none';
  document.getElementById('canvasFeedUrl').value = localStorage.getItem('taskstack-canvas-url') || '';
  const sel = document.getElementById('canvasStackSelect');
  sel.innerHTML = stacks.length === 0 ? `<option value="School">School</option>` : stacks.map(s => `<option value="${s.name}">${s.name}</option>`).join('');
  
  // Reset to Step 1 view
  document.getElementById('canvasStep1').style.display = 'block';
  document.getElementById('canvasStep2').style.display = 'none';
  document.getElementById('btnPreviewCanvas').style.display = 'inline-block';
  document.getElementById('btnSyncCanvas').style.display = 'none';
  document.getElementById('canvasSyncStatus').style.display = 'none';
  
  // Reset include past-due checkbox
  const pastDueCb = document.getElementById('canvasIncludePastDue');
  if (pastDueCb) pastDueCb.checked = false;
  
  document.getElementById('canvasModal').style.display = 'flex';
}

async function submitCanvasPreview() {
  const feedUrl = document.getElementById('canvasFeedUrl').value.trim();
  const targetStack = document.getElementById('canvasStackSelect').value;
  const statusBox = document.getElementById('canvasSyncStatus');
  const previewBtn = document.getElementById('btnPreviewCanvas');
  const includePastDue = document.getElementById('canvasIncludePastDue')?.checked || false;

  if (!feedUrl) return alert("Please paste your Canvas iCal link.");
  localStorage.setItem('taskstack-canvas-url', feedUrl);

  previewBtn.disabled = true;
  statusBox.style.display = 'block';
  statusBox.innerText = includePastDue ? "Inspecting all Canvas tasks (including past-due)..." : "Inspecting upcoming Canvas tasks...";

  try {
    const res = await fetch('/canvas/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        feed_url: feedUrl, 
        target_stack: targetStack,
        include_past_due: includePastDue 
      })
    });
    const data = await res.json();

    if (!res.ok) {
      statusBox.innerText = `Error: ${data.detail || 'Could not inspect feed'}`;
      previewBtn.disabled = false;
      return;
    }

    if (!data.detected_tags || data.detected_tags.length === 0) {
      statusBox.innerText = "No upcoming tasks found in feed.";
      previewBtn.disabled = false;
      return;
    }

    // Render checklist: pre-check existing tags, leave novel tags unchecked
    const listContainer = document.getElementById('canvasTagChecklist');
    listContainer.innerHTML = data.detected_tags.map(item => `
      <label style="display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; padding: 0.3rem 0.5rem; background: rgba(255,255,255,0.7); border-radius: 6px; cursor: pointer;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <input type="checkbox" class="canvas-tag-cb" value="${item.tag}" ${item.already_in_stack ? 'checked' : ''} />
          <span style="font-weight: 700;">${item.tag}</span>
          ${!item.already_in_stack ? '<span style="font-size: 0.7rem; color: #dc2626; font-weight: 700;">(NEW TAG)</span>' : ''}
        </div>
        <span style="color: var(--text-muted); font-size: 0.75rem;">${item.count} upcoming task(s)</span>
      </label>
    `).join('');

    // Switch to Step 2
    document.getElementById('canvasStep1').style.display = 'none';
    document.getElementById('canvasStep2').style.display = 'block';
    previewBtn.style.display = 'none';
    document.getElementById('btnSyncCanvas').style.display = 'inline-block';
    statusBox.style.display = 'none';
  } catch (err) {
    statusBox.innerText = `Network error: ${err.message}`;
  } finally {
    previewBtn.disabled = false;
  }
}

let pendingSyncTargetStack = null;

async function dismissSyncSummaryModal() {
  document.getElementById('syncedSummaryModal').style.display = 'none';
  if (pendingSyncTargetStack) {
    await loadStacks();
    openStackView(pendingSyncTargetStack);
    pendingSyncTargetStack = null;
  }
}

async function submitCanvasSync() {
  const feedUrl = document.getElementById('canvasFeedUrl').value.trim();
  const targetStack = document.getElementById('canvasStackSelect').value;
  const statusBox = document.getElementById('canvasSyncStatus');
  const syncBtn = document.getElementById('btnSyncCanvas');
  const includePastDue = document.getElementById('canvasIncludePastDue')?.checked || false;

  const selectedTags = Array.from(document.querySelectorAll('.canvas-tag-cb:checked')).map(cb => cb.value);

  if (selectedTags.length === 0) {
    return alert("Please select at least one tag to sync, or click Cancel.");
  }

  syncBtn.disabled = true;
  statusBox.style.display = 'block';
  statusBox.innerText = "Syncing approved tasks...";

  try {
    const res = await fetch('/canvas/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        feed_url: feedUrl,
        target_stack: targetStack,
        allowed_tags: selectedTags,
        include_past_due: includePastDue
      })
    });
    const data = await res.json();

    if (res.ok) {
      closeModals();
      syncBtn.disabled = false;
      pendingSyncTargetStack = targetStack;

      // Populate the summary modal
      document.getElementById('syncedSummaryTitle').innerText = `Synced ${data.imported} Task(s)`;
      document.getElementById('syncedSummarySubtitle').innerText = `Added/updated in stack: ${targetStack}`;

      // Populate the summary modal
      const newCount = (data.tasks || []).filter(t => t.change_type === 'new').length;
      const updatedCount = (data.tasks || []).filter(t => t.change_type === 'updated').length;

      document.getElementById('syncedSummaryTitle').innerText = `${data.imported} Task Update(s)`;
      document.getElementById('syncedSummarySubtitle').innerText = `${newCount} new, ${updatedCount} modified in stack: ${targetStack}`;

      const listContainer = document.getElementById('syncedTasksList');
      if (!data.tasks || data.tasks.length === 0) {
        listContainer.innerHTML = `
          <div style="text-align: center; color: var(--text-muted); font-size: 0.9rem; padding: 2rem 1rem;">
            <p style="font-weight: 700; margin-bottom: 0.3rem;">All caught up!</p>
            <p style="font-size: 0.8rem;">No new tasks or deadline changes detected for the selected tags.</p>
          </div>
        `;
      } else {
        listContainer.innerHTML = data.tasks.map(t => {
          const formattedDate = formatDueDate(t.due_date);
          const formattedTime = formatDueTime(t.due_time);
          const isNew = t.change_type === 'new';

          return `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.8rem; background: rgba(255,255,255,0.7); border: 1px solid var(--card-border); border-radius: 8px; font-size: 0.85rem; gap: 0.75rem;">
              <div style="min-width: 0; flex: 1;">
                <div style="display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.2rem;">
                  <span style="font-size: 0.68rem; font-weight: 800; padding: 0.15rem 0.4rem; border-radius: 4px; ${isNew ? 'background: #dcfce7; color: #15803d;' : 'background: #fef3c7; color: #b45309;'}">
                    ${isNew ? 'NEW' : 'UPDATED'}
                  </span>
                  <span style="font-weight: 700; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${t.title}</span>
                </div>
                <span class="tag-badge" style="${getTagStyle(t.course)};">${t.course}</span>
              </div>
              <div style="font-size: 0.78rem; font-weight: 700; color: var(--text-muted); white-space: nowrap; text-align: right;">
                ${formattedDate} ${formattedTime ? `<span style="font-weight: 500;">${formattedTime}</span>` : ''}
              </div>
            </div>
          `;
        }).join('');
      }

      document.getElementById('syncedSummaryModal').style.display = 'flex';
    } else {
      statusBox.innerText = `Error: ${data.detail || 'Could not sync'}`;
      syncBtn.disabled = false;
    }
  } catch (err) {
    statusBox.innerText = `Network error: ${err.message}`;
    syncBtn.disabled = false;
  }
}
