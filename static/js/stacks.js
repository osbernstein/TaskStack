async function loadStacks() {
  const res = await fetch('/stacks');
  stacks = await res.json();
  
  const grid = document.getElementById('stacksListGrid');
  grid.innerHTML = `
    <div class="stack-card" onclick="openStackView('All')">All Tasks</div>
    ${stacks.map(s => `<div class="stack-card" onclick="openStackView('${s.name}')">${s.name}</div>`).join('')}
  `;

  const select = document.getElementById('stackSelect');
  select.innerHTML = stacks.length === 0 
    ? `<option value="General">General</option>` 
    : stacks.map(s => `<option value="${s.name}">${s.name}</option>`).join('');
}

async function handleCreateStack(e) {
  e.preventDefault();
  const name = document.getElementById('newStackInput').value.trim();
  const rawTags = document.getElementById('newStackTagsInput').value.trim();
  const tags = rawTags ? rawTags.split(',').map(t => t.trim()).filter(Boolean) : [];

  const res = await fetch('/stacks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, tags })
  });

  if (res.ok) {
    document.getElementById('newStackInput').value = '';
    document.getElementById('newStackTagsInput').value = '';
    await loadStacks();
    openStackView(name);
  } else {
    const err = await res.json();
    alert(err.detail || 'Could not create stack');
  }
}

async function loadTagsForStack(stackName) {
  const res = await fetch(`/stacks/${encodeURIComponent(stackName)}/tags`);
  currentStackTags = await res.json();

  const sidebar = document.getElementById('sidebarTagsList');
  const addBtn = document.getElementById('sidebarAddTagBtn');
  
  if (addBtn) {
    addBtn.style.display = stackName === 'All' ? 'none' : 'inline-block';
  }

  if (currentStackTags.length === 0) {
    sidebar.innerHTML = `<p style="font-size: 0.78rem; color: var(--text-muted); text-align: center; margin: 1rem 0;">No tags yet.</p>`;
  } else {
    sidebar.innerHTML = currentStackTags.map(t => `
      <div class="tag-row-item" style="${getTagStyle(t)}">
        <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${t}</span>
        ${stackName !== 'All' ? `<button class="tag-pill-btn" title="Delete tag" onclick="deleteTagFromStack('${t}')">&times;</button>` : ''}
      </div>
    `).join('');
  }

  // Inside loadTagsForStack(stackName):
  const filterOptgroup = document.getElementById('filterByTagOptgroup');
  if (filterOptgroup) {
    filterOptgroup.innerHTML = `
      <option value="filter:tag:all">Show All Tags</option>
      ${currentStackTags.map(t => `<option value="filter:tag:${t.toLowerCase()}">${t}</option>`).join('')}
    `;
  }

  // Populate batch selectors
  const filterTagSel = document.getElementById('filterSelectByTag');
  if (filterTagSel) {
    filterTagSel.innerHTML = `<option value="">Choose Tag...</option>` + currentStackTags.map(t => `<option value="${t.toLowerCase()}">${t}</option>`).join('');
  }

  const batchTagSel = document.getElementById('batchTagSelect');
  if (batchTagSel) {
    batchTagSel.innerHTML = `<option value="">Change Tag to...</option>` + currentStackTags.map(t => `<option value="${t}">${t}</option>`).join('');
  }
}

function promptAddNewTag() {
  if (activeStack === 'All') return;
  document.getElementById('addTagModalHeading').innerText = `Add Tag to "${activeStack}"`;
  document.getElementById('newTagNameInput').value = '';
  
  const randomHue = Math.floor(Math.random() * 360);
  document.getElementById('newTagColorPicker').value = hslToHex(randomHue, 75, 45);
  
  document.getElementById('addTagModal').style.display = 'flex';
  document.getElementById('newTagNameInput').focus();
}

async function submitAddNewTagWithColor() {
  const tagName = document.getElementById('newTagNameInput').value.trim();
  const tagColor = document.getElementById('newTagColorPicker').value;

  if (!tagName) return alert("Please provide a tag name.");

  let customColors = {};
  try {
    customColors = JSON.parse(localStorage.getItem('taskstack-tag-colors')) || {};
  } catch (e) {}
  customColors[tagName.toLowerCase()] = tagColor;
  localStorage.setItem('taskstack-tag-colors', JSON.stringify(customColors));

  const res = await fetch(`/stacks/${encodeURIComponent(activeStack)}/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag_name: tagName })
  });

  if (res.ok) {
    closeModals();
    await loadTagsForStack(activeStack);
    await fetchAssignments();
  } else {
    const err = await res.json();
    alert(err.detail || "Could not add tag.");
  }
}

async function deleteTagFromStack(tagName) {
  if (activeStack === 'All') return;

  const matchingTasks = document.querySelectorAll(`input.task-checkbox[data-tag="${tagName.toLowerCase()}"]`).length;

  let confirmMsg = `Are you sure you want to remove tag "${tagName}" from stack "${activeStack}"?`;
  if (matchingTasks > 0) {
    confirmMsg += `\n\nWarning: ${matchingTasks} task(s) currently use this tag and will be reassigned to "General".`;
  }

  if (!confirm(confirmMsg)) return;

  const res = await fetch(`/stacks/${encodeURIComponent(activeStack)}/tags/${encodeURIComponent(tagName)}`, {
    method: 'DELETE'
  });

  if (res.ok) {
    await loadTagsForStack(activeStack);
    await fetchAssignments();
  } else {
    const err = await res.json();
    alert(err.detail || "Could not delete tag.");
  }
}
