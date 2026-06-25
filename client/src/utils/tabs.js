export function getNextTabIndex(currentIndex, key, tabCount) {
  if (tabCount <= 0) return currentIndex;
  if (key === 'ArrowLeft') return (currentIndex - 1 + tabCount) % tabCount;
  if (key === 'ArrowRight') return (currentIndex + 1) % tabCount;
  if (key === 'Home') return 0;
  if (key === 'End') return tabCount - 1;
  return currentIndex;
}
