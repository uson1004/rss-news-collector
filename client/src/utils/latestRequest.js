export function createLatestRequestTracker() {
  let currentRequest = null;

  return {
    start() {
      currentRequest?.controller.abort();
      const controller = new AbortController();
      const request = {
        controller,
        signal: controller.signal,
        isCurrent: () => currentRequest === request,
        finish() {
          if (currentRequest === request) {
            currentRequest = null;
          }
        },
      };
      currentRequest = request;
      return request;
    },
    cancel() {
      currentRequest?.controller.abort();
      currentRequest = null;
    },
  };
}
