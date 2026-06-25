function errorMessageFromPayload(payload) {
  if (typeof payload?.detail === 'string' && payload.detail.trim()) {
    return payload.detail.trim();
  }
  if (Array.isArray(payload?.detail)) {
    const messages = payload.detail
      .map((item) => (typeof item?.msg === 'string' ? item.msg.trim() : ''))
      .filter(Boolean);
    if (messages.length) {
      return messages.join(' ');
    }
  }
  if (typeof payload?.message === 'string' && payload.message.trim()) {
    return payload.message.trim();
  }
  return '';
}

export async function requestJson(url, options = {}, fallbackMessage = '요청을 처리하지 못했어요.', fetchImpl = fetch) {
  let response;
  try {
    response = await fetchImpl(url, options);
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw error;
    }
    throw new Error('서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.', { cause: error });
  }

  const responseText = await response.text();
  let payload = null;
  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch (error) {
      if (!response.ok) {
        throw new Error(fallbackMessage, { cause: error });
      }
      throw new Error('서버 응답을 읽지 못했어요. 잠시 후 다시 시도해 주세요.', { cause: error });
    }
  }

  if (!response.ok) {
    throw new Error(errorMessageFromPayload(payload) || fallbackMessage);
  }
  return payload;
}
