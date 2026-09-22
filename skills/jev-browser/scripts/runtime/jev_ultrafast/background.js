(() => {
  if (window.__jevBridge) return;
  const bridge = window.__jevBridge = {enabled: true, events: []};
  const nativeOpen = window.open;
  const emit = event => bridge.events.push(event);
  const request = (url, target = '_blank', features = '') => {
    let parsed;
    try { parsed = new URL(String(url || ''), location.href); } catch { /* handled below */ }
    if (!url || !parsed || !['http:', 'https:'].includes(parsed.protocol) ||
        features || (target && !['_blank', '_self', '_top', '_parent'].includes(target))) {
      emit({type: 'needs_user', reason: 'This popup requires native window semantics.'});
      return;
    }
    emit({type: 'open', url: parsed.href, referrer: location.href});
  };
  window.open = function(url, target, features) {
    if (!bridge.enabled || ['_self', '_top', '_parent'].includes(target))
      return nativeOpen.call(window, url, target, features);
    request(url, target, features);
    return null; // Only simple URL navigation is supported in background mode.
  };
  document.addEventListener('click', event => {
    if (!bridge.enabled) return;
    const node = event.composedPath().find(e => e instanceof Element);
    if (!node) return;
    if (node.closest('input[type="file"]')) {
      event.preventDefault(); event.stopImmediatePropagation();
      emit({type: 'needs_user', reason: 'File chooser requires user takeover.'});
      return;
    }
    const anchor = node.closest('a[href]');
    if (!anchor || anchor.hasAttribute('download')) return;
    const target = anchor.target || document.querySelector('base[target]')?.target || '';
    if (!target || ['_self', '_top', '_parent'].includes(target)) return;
    event.preventDefault(); event.stopImmediatePropagation();
    request(anchor.href, target);
  }, true);
  document.addEventListener('submit', event => {
    if (!bridge.enabled) return;
    const target = event.submitter?.formTarget || event.target.target;
    if (target && !['_self', '_top', '_parent'].includes(target)) {
      event.preventDefault(); event.stopImmediatePropagation();
      emit({type: 'needs_user', reason: 'Form submission to another window requires user takeover.'});
    }
  }, true);
  for (const name of ['alert', 'confirm', 'prompt']) {
    const original = window[name];
    window[name] = function(...args) {
      if (!bridge.enabled) return original.apply(window, args);
      emit({type: 'needs_user', reason: `Native ${name} requires user takeover.`});
      return name === 'confirm' ? false : name === 'prompt' ? null : undefined;
    };
  }
})();
