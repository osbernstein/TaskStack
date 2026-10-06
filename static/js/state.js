// Shared state used across the UI scripts. Load this file first.
let stacks = [];
let currentStackTags = [];
let activeStack = 'All';
let isEditMode = false;
let currentSortCriterion = 'due_date';
let currentFilterTag = 'all';
let currentFilterStatus = 'all';
let allLoadedTasks = [];
