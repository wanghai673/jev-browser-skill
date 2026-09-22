(() => {
  if (!document.body) return null;
  const cache = window.__jevFast ||= {ids:new WeakMap(), nodes:new Map(), next:1};
  const identity = e => {
    if (!cache.ids.has(e)) cache.ids.set(e,cache.next++);
    const id=cache.ids.get(e); cache.nodes.set(id,e); return id;
  };
  for (const [id,e] of cache.nodes) if (!e.isConnected) cache.nodes.delete(id);
  const sensitive = e => e.type === 'password' ||
    /^(username|current-password|new-password|one-time-code)$/.test(e.autocomplete || '') ||
    /password|passcode|\botp\b|user.?name|login.?id|loginfmt|验证码|密码|短信码|账号|账户|用户名/i.test(
      [e.name,e.id,e.getAttribute('placeholder'),e.getAttribute('aria-label')].filter(Boolean).join(' '));
  const safe = e => !['password','file','hidden'].includes(e.type) && !sensitive(e);
  const visible = e => !e.closest('[aria-hidden="true"],[inert]') &&
    e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true});
  const onScreen = e => {
    const r=e.getBoundingClientRect();
    return visible(e) && r.width>0 && r.height>0 && r.bottom>0 && r.top<innerHeight && r.right>0 && r.left<innerWidth;
  };
  cache.userGate=()=>{
    const reasons=[];
    cache.authFrames=[...document.querySelectorAll('iframe')].filter(e=>onScreen(e) &&
      /captcha|recaptcha|hcaptcha|turnstile|challenge|passport|login|signin/i.test((e.src||'')+' '+e.title))
      .map(e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height,
        path:(()=>{try{const u=new URL(e.src,location.href);return u.origin+u.pathname;}catch{return '';}})()};});
    if ([...document.querySelectorAll('input')].some(e=>sensitive(e) && onScreen(e)))
      reasons.push('Account, password or verification-code entry requires user takeover.');
    if ([...document.querySelectorAll('iframe')].some(e=>onScreen(e) &&
        /captcha|recaptcha|hcaptcha|turnstile|challenge|passport|login|signin/i.test((e.src||'')+' '+e.title)))
      reasons.push('Embedded login or human verification requires user takeover.');
    const t=document.body.innerText;
    if (/verify (that )?you are human|checking your browser|complete the security check|人机验证|滑动.*验证|拖动.*滑块|(?:完成|正在进行)安全验证|验证您不是自动程序|扫码登录|扫描二维码登录/i.test(t))
      reasons.push('Login or human verification requires user takeover.');
    return reasons;
  };
  const name = (e,seen=new Set()) => {
    if (!e || seen.has(e)) return '';
    seen.add(e);
    const referenced=(e.getAttribute('aria-labelledby')||'').split(/\s+/)
      .map(id=>name(document.getElementById(id),seen)).filter(Boolean).join(' ');
    return referenced || e.getAttribute('aria-label') ||
      [...(e.labels||[])].map(l=>name(l,seen)).filter(Boolean).join(' ') ||
      (['button','submit','reset'].includes(e.type) ? e.value : '') || e.getAttribute('alt') ||
      (e.tagName==='INPUT' ? '' : [...e.childNodes].map(n=>n.nodeType===3 ? n.textContent :
        n.nodeType===1 && n.getAttribute('aria-hidden')!=='true' ? name(n,seen) : '').join(' ').trim()) ||
      e.getAttribute('title') || e.getAttribute('placeholder') || '';
  };
  const roles=['button','link','checkbox','radio','switch','tab','menuitem','menuitemradio',
    'option','gridcell','combobox','textbox','searchbox','spinbutton'];
  const selector='a[href],button,input,textarea,select,summary,[contenteditable="true"],'+
    roles.map(role=>'[role="'+role+'"]').join(',');
  const role = e => {
    const explicit=e.getAttribute('role');
    if (roles.includes(explicit)) return explicit;
    if (e.tagName==='BUTTON' || e.tagName==='SUMMARY') return 'button';
    if (e.tagName==='A') return 'link';
    if (e.tagName==='SELECT') return 'combobox';
    if (e.tagName==='TEXTAREA' || e.isContentEditable) return 'textbox';
    if (e.tagName==='INPUT') {
      if (['checkbox','radio'].includes(e.type)) return e.type;
      if (['button','submit','reset','image'].includes(e.type)) return 'button';
      if (e.type==='search') return 'searchbox';
      if (e.type==='number') return 'spinbutton';
      if (['text','email','url','tel'].includes(e.type)) return 'textbox';
    }
    if (e.matches('[onclick],[tabindex]') || getComputedStyle(e).cursor==='pointer') return 'button';
    return null;
  };
  cache.pageKey=()=>[performance.timeOrigin,location.href,scrollX,scrollY,innerWidth,innerHeight,
    [...document.querySelectorAll('input,textarea,select')].filter(safe)
      .map(e=>[identity(e),e.value,e.checked,e.selectedIndex,e.disabled,e.readOnly])];
  cache.guard=e=>{
    if (!e?.isConnected || !visible(e)) return null;
    const scope=e.closest('form,dialog,[role="dialog"],article,li,tr,[role="row"]') || e.parentElement;
    return [identity(e),role(e),name(e),safe(e)?e.value??null:null,e.checked??null,e.selectedIndex??null,
      e.readOnly??null,e.matches(':disabled'),e.getAttribute('aria-disabled'),
      e.getAttribute('aria-expanded'),e.getAttribute('aria-checked'),e.getAttribute('aria-selected'),
      e.getAttribute('href'),scope?.innerText?.slice(0,6000)||''];
  };
  const actions=[];
  const candidates=new Set(document.querySelectorAll(selector+', [onclick], [tabindex]'));
  // Include text controls implemented with framework handlers rather than native buttons.
  for (const e of document.querySelectorAll('div,span,p,li')) {
    if (e.childElementCount===0 && e.textContent.trim() && e.textContent.trim().length<200 &&
        getComputedStyle(e).cursor==='pointer' && !e.closest(selector)) candidates.add(e);
  }
  for (const e of candidates) {
    if (!safe(e) || !visible(e) || e.matches(':disabled') || e.closest('[aria-disabled="true"]')) continue;
    // Focusable layout/group containers are not action targets: their center can hit an unrelated child.
    if (!e.matches(selector) && e.querySelector(selector)) continue;
    const r=e.getBoundingClientRect(), x=r.x+r.width/2, y=r.y+r.height/2, rname=role(e);
    if (!rname || r.width<=0 || r.height<=0 || x<0 || y<0 || x>=innerWidth || y>=innerHeight) continue;
    if (rname==='gridcell' && e.querySelector('button,[role="button"]')) continue;
    let label=name(e);
    if (!label && e.tagName==='A') {
      let parent=e.parentElement;
      for (let depth=0; parent && depth<3 && !label; depth++,parent=parent.parentElement)
        label=parent.innerText.trim().slice(0,500);
      label=label || e.getAttribute('href');
    }
    const base={node:identity(e),role:rname,label:label||rname,
      rect:{x:r.x,y:r.y,w:r.width,h:r.height}};
    if (e.tagName==='A' && e.hasAttribute('href')) base.href=e.href;
    for (const key of ['checked','selected','expanded']) {
      const value=e.getAttribute('aria-'+key);
      if (value!==null) base[key]=value;
    }
    if (['checkbox','radio'].includes(e.type)) base.checked=String(e.checked);
    if (e.tagName==='SELECT') {
      for (const o of e.options) if (!o.selected && !o.disabled && !o.closest('optgroup[disabled]'))
        actions.push({...base,kind:'select',value:o.value,
          current_value:[...e.selectedOptions].map(o=>o.label).join(', '),label:base.label+' → '+o.label});
    } else {
      const editable=!e.readOnly && e.getAttribute('aria-readonly')!=='true' &&
        (['textbox','searchbox','spinbutton'].includes(rname) ||
          (rname==='combobox' && ['INPUT','TEXTAREA'].includes(e.tagName)));
      const value='value' in e ? String(e.value) :
        e.isContentEditable || rname==='combobox' ? e.innerText.trim() : '';
      actions.push({...base,kind:editable?'fill':'click',value});
      if (editable) actions.push({...base,kind:'click',value,label:'Open '+base.label});
    }
  }
  const words=[], walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  const range=document.createRange(); let node,length=0;
  while ((node=walker.nextNode()) && length<6000) {
    const value=node.textContent.trim(), parent=node.parentElement;
    if (!value || !parent || parent.closest('script,style,noscript,template') || !visible(parent)) continue;
    range.selectNodeContents(node); const r=range.getBoundingClientRect();
    if (r.width>0 && r.height>0 && r.bottom>0 && r.top<innerHeight && r.right>0 && r.left<innerWidth) {
      words.push(value); length+=value.length;
    }
  }
  const text=words.join('\n').slice(0,6000), height=document.documentElement.scrollHeight;
  const media=[...document.querySelectorAll('video,audio')].map(e=>({
    kind:e.tagName.toLowerCase(), node:identity(e), src:e.currentSrc, paused:e.paused, ended:e.ended,
    current_time:e.currentTime, ready_state:e.readyState,
    playing:!e.paused && !e.ended && e.readyState>=2 && e.currentTime>0,
    duration:Number.isFinite(e.duration)?e.duration:null
  }));
  const page_key=cache.pageKey(), guards={};
  for (const a of actions) if (!(a.node in guards)) guards[a.node]=cache.guard(cache.nodes.get(a.node));
  // Compare meaning and identity. Geometry is always resolved and hit-tested just before input.
  const semantics=actions.map(({rect,...action})=>action);
  const marker=[performance.timeOrigin,location.href,scrollX,scrollY,innerWidth,innerHeight,
    document.title,text,semantics,page_key[6],media.map(m=>[m.paused,m.ended,m.ready_state])];
  const omitted_actions=Math.max(0,actions.length-250);
  actions.splice(250);
  actions.forEach((a,i)=>a.id='e'+(i+1));
  if (scrollY+innerHeight<height-2) actions.push({id:'scroll_down',kind:'scroll',label:'Scroll down',delta:560});
  if (scrollY>0) actions.push({id:'scroll_up',kind:'scroll',label:'Scroll up',delta:-560});
  actions.push({id:'wait',kind:'wait',label:'Wait for the page to update'});
  return {url:location.href,title:document.title,w:innerWidth,h:innerHeight,text,
    scroll:{y:scrollY,height},actions,marker,page_key,guards,omitted_actions,media,
    document_id:performance.timeOrigin,user_action_required:cache.userGate(),auth_frames:cache.authFrames};
})()
