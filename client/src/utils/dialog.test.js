import assert from 'node:assert/strict';
import test from 'node:test';

import { getDialogFocusTargetIndex, shouldCloseDialog } from './dialog.js';

test('Escape requests dialog closure', () => {
  assert.equal(shouldCloseDialog('Escape'), true);
  assert.equal(shouldCloseDialog('Enter'), false);
});

test('wraps focus at both ends of a dialog', () => {
  assert.equal(getDialogFocusTargetIndex(2, false, 3), 0);
  assert.equal(getDialogFocusTargetIndex(0, true, 3), 2);
});

test('does not redirect focus inside the dialog', () => {
  assert.equal(getDialogFocusTargetIndex(1, false, 3), null);
  assert.equal(getDialogFocusTargetIndex(0, false, 0), null);
});
