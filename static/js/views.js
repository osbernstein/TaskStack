function hideAllViews() {
  document.getElementById('homeView').style.display = 'none';
  document.getElementById('stacksView').style.display = 'none';
  document.getElementById('createView').style.display = 'none';
  document.getElementById('listView').style.display = 'none';
}

function showHomeView() { hideAllViews(); document.getElementById('homeView').style.display = 'grid'; }

function showStacksView() { hideAllViews(); document.getElementById('stacksView').style.display = 'block'; loadStacks(); }

async function openStackView(stackName) {
  activeStack = stackName;
  isEditMode = false;
  currentSortCriterion = 'due_date';
  currentFilterTag = 'all';
  currentFilterStatus = 'all';

  const sortSel = document.getElementById('sortCriterionSelect');
  if (sortSel) sortSel.selectedIndex = 0; // displays "Filter" placeholder

  document.getElementById('batchActionBar').style.display = 'none';
  document.getElementById('btnToggleEdit').innerText = 'Edit';
  document.getElementById('currentStackHeading').innerText = stackName === 'All' ? 'All Tasks' : stackName;
  hideAllViews();
  document.getElementById('listView').style.display = 'block';
  await loadTagsForStack(stackName);
  await fetchAssignments();
}
