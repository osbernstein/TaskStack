// Startup: restore the saved theme color and load stacks. Load this file last.
const savedHex = localStorage.getItem('taskstack-hex') || '#0284c7';
applyDynamicColor(savedHex);
loadStacks();
