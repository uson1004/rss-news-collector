export function normalizeArticleInput(value) {
  const trimmed = String(value ?? '').trim();
  if (!trimmed) {
    throw new Error('읽을 웹페이지 URL을 입력해 주세요.');
  }

  const candidate = /^[a-z][a-z\d+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  let parsed;
  try {
    parsed = new URL(candidate);
  } catch (error) {
    throw new Error('유효한 웹페이지 URL을 입력해 주세요.', { cause: error });
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('HTTP 또는 HTTPS 웹페이지 URL만 사용할 수 있어요.');
  }
  return parsed.toString();
}
