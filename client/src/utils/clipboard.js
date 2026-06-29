export async function copyTextToClipboard(text, environment = globalThis) {
  const value = String(text ?? '');
  if (!value) return false;

  try {
    if (environment.navigator?.clipboard?.writeText) {
      await environment.navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    // Fall through to the legacy copy surface below.
  }

  const documentRef = environment.document;
  if (!documentRef?.createElement || !documentRef.body?.appendChild || !documentRef.execCommand) {
    return false;
  }

  const textarea = documentRef.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.inset = '0 auto auto 0';
  textarea.style.opacity = '0';
  documentRef.body.appendChild(textarea);
  textarea.select();

  try {
    return Boolean(documentRef.execCommand('copy'));
  } catch {
    return false;
  } finally {
    textarea.remove();
  }
}
