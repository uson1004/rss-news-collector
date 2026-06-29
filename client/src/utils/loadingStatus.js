export function hasLoadingStatus(statuses) {
  return Array.isArray(statuses) && statuses.includes('loading');
}
