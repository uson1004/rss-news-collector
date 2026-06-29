const SETTING_LIMITS = {
  fontSize: [15, 24],
  lineHeight: [1.45, 2.15],
  paragraphSpacing: [0.8, 2.4],
  contentWidth: [560, 860],
};

const THEMES = new Set(['light', 'dark', 'contrast']);

function boundedNumber(value, fallback, [min, max]) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, value));
}

export function normalizeReaderSettings(settings, defaults) {
  const candidate = settings && typeof settings === 'object' ? settings : {};
  return {
    fontSize: boundedNumber(candidate.fontSize, defaults.fontSize, SETTING_LIMITS.fontSize),
    lineHeight: boundedNumber(candidate.lineHeight, defaults.lineHeight, SETTING_LIMITS.lineHeight),
    paragraphSpacing: boundedNumber(
      candidate.paragraphSpacing,
      defaults.paragraphSpacing,
      SETTING_LIMITS.paragraphSpacing,
    ),
    contentWidth: boundedNumber(candidate.contentWidth, defaults.contentWidth, SETTING_LIMITS.contentWidth),
    theme: THEMES.has(candidate.theme) ? candidate.theme : defaults.theme,
  };
}
