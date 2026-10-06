async function updateTagChoicesForTaskForm() {
  const stackSel = document.getElementById('stackSelect');
  if (!stackSel || !stackSel.value) return;

  const selectedStack = stackSel.value;
  const res = await fetch(`/stacks/${encodeURIComponent(selectedStack)}/tags`);
  const tags = await res.json();
  const tagSel = document.getElementById('courseTagSelect');

  if (!tags || tags.length === 0) {
    tagSel.innerHTML = `<option value="General">General</option>`;
  } else {
    tagSel.innerHTML = tags.map(t => `<option value="${t}">${t}</option>`).join('');
  }
}

function showCreateTaskView() {
  hideAllViews();
  const form = document.getElementById('createTaskForm');
  if (form) form.reset();

  // Reset specific helper fields
  document.getElementById('customCourseTagInput').value = '';
  document.getElementById('due_time').value = '23:59';
  
  // Default to today's date if empty
  const todayStr = new Date().toISOString().split('T')[0];
  document.getElementById('due_date').value = todayStr;

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
  const customTag = document.getElementById('customCourseTagInput').value.trim();
  const dropdownTag = document.getElementById('courseTagSelect').value;
  const finalCourse = customTag || dropdownTag || 'General';
  const targetStack = document.getElementById('stackSelect').value;

  // If user typed a custom tag, register it with the stack so it persists in the sidebar & dropdowns
  if (customTag) {
    await fetch(`/stacks/${encodeURIComponent(targetStack)}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag_name: customTag })
    });
  }

  const payload = {
    title: document.getElementById('title').value.trim(),
    course: finalCourse,
    stack_name: targetStack,
    due_date: document.getElementById('due_date').value,
    due_time: document.getElementById('due_time').value || null,
    link: document.getElementById('link').value.trim() || null,
    status: 'not_started'
  };

  const res = await fetch('/assignments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    e.target.reset();
    await loadTagsForStack(payload.stack_name);
    openStackView(payload.stack_name);
  } else {
    const err = await res.json();
    alert(err.detail || 'Could not create task.');
  }
});
