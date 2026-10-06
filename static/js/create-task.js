let currentTagOptions = `<option value="General">General</option>`;

async function updateTagChoicesForTaskForm() {
  const stackSel = document.getElementById('stackSelect');
  if (!stackSel || !stackSel.value) return;

  const selectedStack = stackSel.value;
  const res = await fetch(`/stacks/${encodeURIComponent(selectedStack)}/tags`);
  const tags = await res.json();

  currentTagOptions = (!tags || tags.length === 0)
    ? `<option value="General">General</option>`
    : tags.map(t => `<option value="${t}">${t}</option>`).join('');

  // Refresh every task row's tag picker, keeping current picks where possible
  document.querySelectorAll('#createTaskForm .tag-choice').forEach(sel => {
    const prev = sel.value;
    sel.innerHTML = currentTagOptions;
    if ([...sel.options].some(o => o.value === prev)) sel.value = prev;
  });
  syncSharedTag();
}

// --- Multi-Task Rows ---
function addTaskRow() {
  const rows = document.getElementById('taskRows');
  const row = document.getElementById('taskRowTemplate').content.firstElementChild.cloneNode(true);
  row.querySelector('.row-tag-select').innerHTML = currentTagOptions;

  // New rows start on the previous row's due date (or today for the first row)
  const last = rows.lastElementChild;
  row.querySelector('.row-due-date').value = last
    ? last.querySelector('.row-due-date').value
    : new Date().toISOString().split('T')[0];

  rows.appendChild(row);
  renumberTaskRows();
  syncSharedTag();
  if (last) row.querySelector('.row-title').focus();
}

function removeTaskRow(btn) {
  btn.closest('.task-row').remove();
  renumberTaskRows();
  syncSharedTag();  // if Task 1 was removed, the new Task 1 becomes the tag source
}

function renumberTaskRows() {
  const rows = document.querySelectorAll('#taskRows .task-row');
  rows.forEach((r, i) => r.querySelector('.task-row-label').textContent = `Task ${i + 1}`);
  document.getElementById('createTasksBtn').textContent =
    rows.length > 1 ? `Add ${rows.length} Tasks to Stack` : 'Add Task to Stack';
}

// When "use Task 1's tag" is checked, copy Task 1's tag into every other row and lock their pickers
function syncSharedTag() {
  const on = document.getElementById('useSharedTag').checked;
  const rows = [...document.querySelectorAll('#taskRows .task-row')];
  if (rows.length === 0) return;
  const firstSel = rows[0].querySelector('.row-tag-select');
  const firstInput = rows[0].querySelector('.row-tag-input');

  rows.forEach((r, i) => {
    const sel = r.querySelector('.row-tag-select');
    const input = r.querySelector('.row-tag-input');
    const locked = on && i > 0;
    sel.disabled = input.disabled = locked;
    if (locked) {
      sel.value = firstSel.value;
      input.value = firstInput.value;
    }
  });
}

function showCreateTaskView() {
  hideAllViews();
  const form = document.getElementById('createTaskForm');
  if (form) form.reset();

  // Start with a single empty task row
  document.getElementById('taskRows').innerHTML = '';
  addTaskRow();

  document.getElementById('createView').style.display = 'block';

  // Pre-select active stack if not 'All'
  const stackSel = document.getElementById('stackSelect');
  if (activeStack !== 'All' && stackSel) {
    stackSel.value = activeStack;
  }

  updateTagChoicesForTaskForm();
}

document.getElementById('createTaskForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const targetStack = document.getElementById('stackSelect').value;
  const useShared = document.getElementById('useSharedTag').checked;
  const rows = [...document.querySelectorAll('#taskRows .task-row')];
  const tagOf = r => r.querySelector('.row-tag-input').value.trim() || r.querySelector('.row-tag-select').value || 'General';
  const firstTag = tagOf(rows[0]);

  const tasks = rows.map(r => ({
    title: r.querySelector('.row-title').value.trim(),
    course: useShared ? firstTag : tagOf(r),
    due_date: r.querySelector('.row-due-date').value,
    due_time: r.querySelector('.row-due-time').value || null,
    link: r.querySelector('.row-link').value.trim() || null
  }));

  // The server registers any new tags with the stack, so no separate tag call is needed
  const res = await fetch('/assignments/batch/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stack_name: targetStack, tasks })
  });

  if (res.ok) {
    e.target.reset();
    await loadTagsForStack(targetStack);
    openStackView(targetStack);
  } else {
    const err = await res.json();
    alert(typeof err.detail === 'string' ? err.detail : 'Could not create tasks.');
  }
});
