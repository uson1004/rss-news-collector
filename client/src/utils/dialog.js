export function shouldCloseDialog(key) {
  return key === 'Escape';
}

export function getDialogFocusTargetIndex(currentIndex, shiftKey, focusableCount) {
  if (focusableCount <= 0) return null;
  if (shiftKey && currentIndex <= 0) return focusableCount - 1;
  if (!shiftKey && currentIndex >= focusableCount - 1) return 0;
  return null;
}
