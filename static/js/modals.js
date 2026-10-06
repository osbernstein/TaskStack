function toggleSettings(e) {
  e.stopPropagation();
  const menu = document.getElementById('settingsDropdown');
  menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
}

window.onclick = () => {
  const dd = document.getElementById('settingsDropdown');
  if (dd) dd.style.display = 'none';
};

function closeModals() {
  document.querySelectorAll('.modal-overlay').forEach(el => el.style.display = 'none');
}

function openColorModal() { 
  document.getElementById('settingsDropdown').style.display = 'none'; 
  document.getElementById('colorModal').style.display = 'flex'; 
}

function openDeleteModal() {
  document.getElementById('settingsDropdown').style.display = 'none';
  const sel = document.getElementById('deleteStackSelect');
  sel.innerHTML = stacks.map(s => `<option value="${s.name}">${s.name}</option>`).join('');
  document.getElementById('deleteModal').style.display = 'flex';
}

function openMergeModal() {
  document.getElementById('settingsDropdown').style.display = 'none';
  const s1 = document.getElementById('mergeSourceSelect');
  const s2 = document.getElementById('mergeTargetSelect');
  s1.innerHTML = stacks.map(s => `<option value="${s.name}">${s.name}</option>`).join('');
  s2.innerHTML = stacks.map((s, idx) => `<option value="${s.name}" ${idx === 1 ? 'selected' : ''}>${s.name}</option>`).join('');
  document.getElementById('mergeModal').style.display = 'flex';
}

async function confirmDeleteStack() {
  const stackName = document.getElementById('deleteStackSelect').value;
  const deleteTasks = document.getElementById('deleteTasksCheckbox').checked;
  if (!confirm(`Are you sure you want to delete stack "${stackName}"?`)) return;

  const res = await fetch(`/stacks/${encodeURIComponent(stackName)}?delete_tasks=${deleteTasks}`, { method: 'DELETE' });
  if (res.ok) {
    closeModals();
    await loadStacks();
    showStacksView();
  }
}

async function confirmMergeStacks() {
  const source = document.getElementById('mergeSourceSelect').value;
  const target = document.getElementById('mergeTargetSelect').value;
  if (source === target) return alert("Source and target must be different.");

  const res = await fetch('/stacks/merge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_stack: source, target_stack: target })
  });
  if (res.ok) {
    closeModals();
    openStackView(target);
  }
}
