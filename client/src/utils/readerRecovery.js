export function getReaderRecoveryOptions(canRetry) {
  const options = [
    { id: 'url', label: '다른 URL 입력', route: '/url' },
    { id: 'news', label: '뉴스로 돌아가기', route: '/news' },
  ];
  return canRetry ? [{ id: 'retry', label: '다시 시도' }, ...options] : options;
}
