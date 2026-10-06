function handleSortFilterChange(val) {
  // 1. Always wipe state back to pure "Default" baseline first
  currentSortCriterion = 'due_date';
  currentFilterTag = 'all';
  currentFilterStatus = 'all';

  // 2. Apply ONLY the single selected rule
  if (val === 'default') {
    // Already at baseline (due_date sort + done tasks pinned to bottom)
  } else if (val.startsWith('filter:tag:')) {
    currentFilterTag = val.replace('filter:tag:', '').toLowerCase();
  } else if (val.startsWith('filter:status:')) {
    currentFilterStatus = val.replace('filter:status:', '');
  } else if (val.startsWith('sort:')) {
    currentSortCriterion = val.replace('sort:', '');
  }

  fetchAssignments();
}

async function fetchAssignments() {
  let url = new URL('/assignments', window.location.origin);
  if (activeStack !== 'All') url.searchParams.append('stack', activeStack);

  const res = await fetch(url);
  let tasks = await res.json();
  allLoadedTasks = tasks;
  const container = document.getElementById('tasksContainer');

  // 1. Apply Tag Filter
  if (currentFilterTag !== 'all') {
    tasks = tasks.filter(t => (t.course || '').trim().toLowerCase() === currentFilterTag);
  }

  // 2. Apply Status Filter
  if (currentFilterStatus !== 'all') {
    tasks = tasks.filter(t => t.status === currentFilterStatus);
  }

  if (tasks.length === 0) {
    container.innerHTML = `<p style="color: var(--text-muted); text-align: center; margin: 3rem 0;">No tasks found.</p>`;
    return;
  }

  const statusWeight = {
    'not_started': 0,
    'in_progress': 1,
    'done': 2
  };

  tasks.sort((a, b) => {
    // 1. "pure_due_date": strictly chronological, ignoring status
    if (currentSortCriterion === 'pure_due_date') {
      const dateComp = (a.due_date || '').localeCompare(b.due_date || '');
      if (dateComp !== 0) return dateComp;
      return (a.due_time || '').localeCompare(b.due_time || '');
    }

    // 2. "course": keep all tasks with the SAME tag together
    if (currentSortCriterion === 'course') {
      const courseComp = (a.course || '').localeCompare(b.course || '', undefined, { sensitivity: 'base' });
      if (courseComp !== 0) return courseComp;

      // Within the same tag, place done tasks at the end of that tag group
      const aDone = a.status === 'done';
      const bDone = b.status === 'done';
      if (aDone && !bDone) return 1;
      if (!aDone && bDone) return -1;

      // Within the same tag and status group, sort by due date
      const dateComp = (a.due_date || '').localeCompare(b.due_date || '');
      if (dateComp !== 0) return dateComp;
      return (a.due_time || '').localeCompare(b.due_time || '');
    }

    // 3. For Default and Sort by Status: push done tasks to the bottom of the entire stack
    const aDone = a.status === 'done';
    const bDone = b.status === 'done';

    if (aDone && !bDone) return 1;
    if (!aDone && bDone) return -1;

    if (currentSortCriterion === 'due_date') {
      const dateComp = (a.due_date || '').localeCompare(b.due_date || '');
      if (dateComp !== 0) return dateComp;
      return (a.due_time || '').localeCompare(b.due_time || '');
    }

    if (currentSortCriterion === 'status') {
      const weightDiff = (statusWeight[a.status] ?? 0) - (statusWeight[b.status] ?? 0);
      if (weightDiff !== 0) return weightDiff;
      return (a.due_date || '').localeCompare(b.due_date || '');
    }

    return 0;
  });

  container.innerHTML = tasks.map(t => {
    const formattedDate = formatDueDate(t.due_date);
    const formattedTime = formatDueTime(t.due_time);
    const hasDate = Boolean(t.due_date && t.due_date.trim() !== '');

    const { isOverdue, isDueSoon } = getDueUrgency(t.due_date, t.due_time, t.status);

    return `
      <div class="task-card">
        <input type="checkbox" class="task-checkbox" value="${t.id}" data-tag="${t.course.toLowerCase()}" style="${isEditMode ? 'display: block;' : 'display: none;'}" />

        <!-- Main Content: Title & Tag Badges -->
        <div style="flex-grow: 1; min-width: 0;">
          <div style="font-weight: 600; font-size: 0.98rem; color: var(--text); margin-bottom: 0.2rem; ${t.status === 'done' ? 'text-decoration: line-through; opacity: 0.5;' : ''}" class="${isDueSoon ? 'due-soon-text' : ''}">
            ${isOverdue ? '<span class="badge-late">&#9888; LATE</span> ' : ''}
            <span onclick="openEditTaskModal(${t.id})" style="cursor: pointer; text-decoration-line: ${t.status === 'done' ? 'line-through' : 'none'};" title="Click to edit task">
              ${t.title}
            </span>
          </div>
          <div class="meta">
            <span class="tag-badge" style="background: rgba(0,0,0,0.05); color: var(--text);">${t.stack_name}</span>

            <!-- Tag Dropdown Switcher -->
            <span class="tag-badge" id="tag-badge-${t.id}" style="${getTagStyle(t.course)}" onclick="showInlineTagSelect(${t.id})">
              ${t.course}
            </span>
            <select class="tag-select-inline" id="tag-select-${t.id}" onchange="reassignTaskTag(${t.id}, this.value)">
              ${currentStackTags.map(tag => `<option value="${tag}" ${tag === t.course ? 'selected' : ''}>${tag}</option>`).join('')}
            </select>

            ${t.link ? `<a href="${t.link}" target="_blank" style="color: var(--accent); font-weight: 700;">Link &rarr;</a>` : ''}
          </div>
        </div>

        <!-- Inline Due Date & Time Badge -->
        <div class="due-badge ${hasDate ? '' : 'no-date'} ${isDueSoon ? 'due-soon' : ''} ${isOverdue ? 'due-soon' : ''}">
          <span>${formattedDate}</span>
          ${formattedTime ? `<span class="due-time-inline ${(isDueSoon || isOverdue) ? 'due-soon-text' : ''}">${formattedTime}</span>` : ''}
        </div>

        <!-- Status & Action Controls -->
        <div class="actions">
          <select class="status-select ${t.status}" onchange="updateStatus(${t.id}, this.value, this)">
            <option value="not_started" ${t.status === 'not_started' ? 'selected' : ''}>Not Started</option>
            <option value="in_progress" ${t.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
            <option value="done" ${t.status === 'done' ? 'selected' : ''}>Done</option>
          </select>
          <button class="btn-delete" title="Delete Task" onclick="deleteTask(${t.id})">&times;</button>
        </div>
      </div>
    `;
  }).join('');
}

function showInlineTagSelect(taskId) {
  document.getElementById(`tag-badge-${taskId}`).style.display = 'none';
  const sel = document.getElementById(`tag-select-${taskId}`);
  sel.style.display = 'inline-block';
  sel.focus();
}

// Update fetchAssignments to store current tasks cache
// Inside fetchAssignments(), right after: let tasks = await res.json();
// Add: allLoadedTasks = tasks;

async function openEditTaskModal(taskId) {
  const task = allLoadedTasks.find(t => t.id === taskId);
  if (!task) return;

  document.getElementById('editTaskId').value = task.id;
  document.getElementById('editTaskTitle').value = task.title;
  document.getElementById('editTaskDueDate').value = task.due_date || '';
  document.getElementById('editTaskDueTime').value = task.due_time || '23:59';
  document.getElementById('editTaskLink').value = task.link || '';
  document.getElementById('editTaskTagCustom').value = '';

  // Populate stacks dropdown
  const stackSel = document.getElementById('editTaskStack');
  stackSel.innerHTML = stacks.length === 0
    ? `<option value="General">General</option>`
    : stacks.map(s => `<option value="${s.name}" ${s.name === task.stack_name ? 'selected' : ''}>${s.name}</option>`).join('');

  await updateTagChoicesForEditModal(task.course);

  document.getElementById('editTaskModal').style.display = 'flex';
}

async function updateTagChoicesForEditModal(selectedCourseTag = null) {
  const selectedStack = document.getElementById('editTaskStack').value;
  const res = await fetch(`/stacks/${encodeURIComponent(selectedStack)}/tags`);
  const tags = await res.json();
  const tagSel = document.getElementById('editTaskTagSelect');
  
  const currentSelected = selectedCourseTag || tagSel.value;
  tagSel.innerHTML = tags.map(t => `<option value="${t}" ${t === currentSelected ? 'selected' : ''}>${t}</option>`).join('');

  // If the task has a tag not registered in the stack, add it as an option
  if (currentSelected && !tags.includes(currentSelected)) {
    tagSel.innerHTML = `<option value="${currentSelected}" selected>${currentSelected}</option>` + tagSel.innerHTML;
  }
}

async function handleEditTaskSubmit(e) {
  e.preventDefault();
  const taskId = document.getElementById('editTaskId').value;
  const customTag = document.getElementById('editTaskTagCustom').value.trim();
  const dropdownTag = document.getElementById('editTaskTagSelect').value;
  const finalCourse = customTag || dropdownTag || 'General';

  const payload = {
    title: document.getElementById('editTaskTitle').value.trim(),
    stack_name: document.getElementById('editTaskStack').value,
    course: finalCourse,
    due_date: document.getElementById('editTaskDueDate').value,
    due_time: document.getElementById('editTaskDueTime').value || null,
    link: document.getElementById('editTaskLink').value.trim() || null
  };

  const res = await fetch(`/assignments/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    closeModals();
    if (payload.stack_name !== activeStack && activeStack !== 'All') {
      openStackView(payload.stack_name);
    } else {
      await loadTagsForStack(activeStack);
      fetchAssignments();
    }
  } else {
    const err = await res.json();
    alert(err.detail || 'Could not update task.');
  }
}

async function reassignTaskTag(taskId, newTag) {
  await fetch(`/assignments/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ course: newTag })
  });
  fetchAssignments();
}

async function updateStatus(id, nextStatus, el) {
  if (el) {
    el.className = `status-select ${nextStatus}`;
  }
  await fetch(`/assignments/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: nextStatus })
  });
  fetchAssignments();
}

async function deleteTask(id) {
  if (confirm('Delete this task?')) {
    await fetch(`/assignments/${id}`, { method: 'DELETE' });
    fetchAssignments();
  }
}

// Formats YYYY-MM-DD -> MM/DD/YY with fallbacks
function formatDueDate(dateStr) {
  if (!dateStr || dateStr.trim() === '') return 'No Due Date';
  const parts = dateStr.trim().split('-');
  if (parts.length === 3) {
    const [year, month, day] = parts;
    const shortYear = year.slice(-2);
    return `${month}/${day}/${shortYear}`;
  }
  return dateStr;
}

// Formats 24h HH:MM -> 12h civilian time (e.g. 11:59 PM), omitting if missing or blank
function formatDueTime(timeStr) {
  if (!timeStr || timeStr.trim() === '') return '';
  const parts = timeStr.trim().split(':');
  if (parts.length >= 2) {
    let hour = parseInt(parts[0], 10);
    const minute = parts[1];
    if (isNaN(hour)) return timeStr;
    const ampm = hour >= 12 ? 'PM' : 'AM';
    hour = hour % 12 || 12;
    return `${hour}:${minute} ${ampm}`;
  }
  return timeStr;
}

function getDueUrgency(dateStr, timeStr, status) {
  if (!dateStr || dateStr.trim() === '' || status === 'done') {
    return { isOverdue: false, isDueSoon: false };
  }

  const timePart = (timeStr && timeStr.trim() !== '') ? timeStr.trim() : '23:59';
  // Construct deadline date object
  const deadline = new Date(`${dateStr.trim()}T${timePart.length === 5 ? timePart + ':00' : timePart}`);
  
  if (isNaN(deadline.getTime())) {
    return { isOverdue: false, isDueSoon: false };
  }

  const now = new Date();
  const diffMs = deadline - now;
  const hoursLeft = diffMs / (1000 * 60 * 60);

  const isOverdue = diffMs < 0;
  const isDueSoon = !isOverdue && hoursLeft <= 24;

  return { isOverdue, isDueSoon };
}
