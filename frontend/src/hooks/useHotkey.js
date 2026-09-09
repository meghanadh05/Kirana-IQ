import { useEffect } from 'react';

/**
 * Bind a keyboard shortcut at the document level.
 *
 * Ignores keystrokes typed into a field unless `allowInInput` is set, so ⌘K
 * works everywhere but a plain "n" does not fire while filling in a form.
 */
export function useHotkey(combo, handler, { allowInInput = false, enabled = true } = {}) {
  useEffect(() => {
    if (!enabled) return undefined;

    const parts = combo.toLowerCase().split('+');
    const key = parts[parts.length - 1];
    const wantsMod = parts.includes('mod');
    const wantsShift = parts.includes('shift');

    function onKeyDown(event) {
      const target = event.target;
      const typing =
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable);

      if (typing && !allowInInput) return;

      const mod = event.metaKey || event.ctrlKey;
      if (wantsMod !== mod) return;
      if (wantsShift !== event.shiftKey) return;
      if (event.key.toLowerCase() !== key) return;

      event.preventDefault();
      handler(event);
    }

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [combo, handler, allowInInput, enabled]);
}
