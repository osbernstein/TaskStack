function toggleEditMode() {
  isEditMode = !isEditMode;
  document.getElementById('batchActionBar').style.display = isEditMode ? 'flex' : 'none';
  document.getElementById('btnToggleEdit').innerText = isEditMode ? 'Done' : 'Edit';
  
  const filterSel = document.getElementById('filterSelectByTag');
  if (filterSel) filterSel.value = '';
  
  const selectAllCb = document.getElementById('selectAllCheckbox');
  if (selectAllCb) selectAllCb.checked = false;

  document.querySelectorAll('.task-checkbox').forEach(cb => {
    cb.style.display = isEditMode ? 'block' : 'none';
    if (!isEditMode) cb.checked = false;
  });
}

function toggleSelectAll(checked) {
  document.querySelectorAll('.task-checkbox').forEach(cb => cb.checked = checked);
}

function selectTasksByTag(tagValue) {
  const selectAllCb = document.getElementById('selectAllCheckbox');
  const checkboxes = document.querySelectorAll('.task-checkbox');

  if (!tagValue) {
    checkboxes.forEach(cb => cb.checked = false);
    if (selectAllCb) selectAllCb.checked = false;
    return;
  }

  let matchCount = 0;
  checkboxes.forEach(cb => {
    if (cb.dataset.tag === tagValue.toLowerCase()) {
      cb.checked = true;
      matchCount++;
    } else {
      cb.checked = false;
    }
  });

  if (selectAllCb) {
    selectAllCb.checked = matchCount > 0 && matchCount === checkboxes.length;
  }
}

function getSelectedTaskIds() {
  return Array.from(document.querySelectorAll('.task-checkbox:checked')).map(cb => parseInt(cb.value));
}

async function applyBatchStatus() {
  const task_ids = getSelectedTaskIds();
  const status = document.getElementById('batchStatusSelect').value;
  if (!task_ids.length || !status) return alert('Select tasks and a status.');

  await fetch('/assignments/batch/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_ids, status })
  });
  fetchAssignments();
}

async function applyBatchTag() {
  const task_ids = getSelectedTaskIds();
  const course = document.getElementById('batchTagSelect').value;
  if (!task_ids.length || !course) return alert('Select tasks and a tag.');

  await fetch('/assignments/batch/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_ids, course })
  });
  fetchAssignments();
}

async function deleteSelectedTasks() {
  const task_ids = getSelectedTaskIds();
  if (!task_ids.length) return alert('Select tasks to delete.');
  if (!confirm(`Delete ${task_ids.length} selected tasks?`)) return;

  await fetch('/assignments/batch/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_ids })
  });
  fetchAssignments();
}
