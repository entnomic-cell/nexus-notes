(function(){
  function safeText(value){ return String(value||'').trim(); }
  function getTargetElement(target){
    if(target instanceof Element)return target;
    if(target && target.parentElement instanceof Element)return target.parentElement;
    return null;
  }
  function getEditorBlock(target){
    const editor=document.getElementById('editor-content');
    let node=getTargetElement(target);
    while(node && node!==editor){
      if(node.parentElement===editor)return node;
      node=node.parentElement;
    }
    return null;
  }
  function makeAction(label,opts){
    opts=opts||{};
    return {
      id:opts.id || ('ctx-'+label.toLowerCase().replace(/[^a-z0-9]+/g,'-')),
      label,
      icon:opts.icon || 'document',
      hint:opts.hint || '',
      keywords:[label.toLowerCase()].concat(opts.keywords||[]).join(' '),
      run:typeof opts.run==='function' ? opts.run : null,
      children:Array.isArray(opts.children)?opts.children:null,
      disabled:!!opts.disabled
    };
  }
  function downloadHref(href,fileName){
    if(!href)return;
    const a=document.createElement('a');
    a.href=href;
    a.download=fileName||'download';
    a.rel='noopener';
    a.click();
  }
  function buildSketchPreview(doc){
    const source=serializeSketchDoc(doc||defaultSketchDoc());
    const off=document.createElement('canvas');
    off.width=1600;off.height=1000;
    const ctx=off.getContext('2d');
    ctx.fillStyle='#0b1220';
    ctx.fillRect(0,0,off.width,off.height);
    const fit=fitSketchViewport(source,off.width,off.height,120);
    ctx.translate(fit.x,fit.y);
    ctx.scale(fit.zoom,fit.zoom);
    getPrimarySketchBlock(source).strokes.forEach(stroke=>drawSketchStroke(ctx,stroke,false));
    return off.toDataURL('image/png');
  }
  function duplicateBlock(el){
    if(!el)return;
    const clone=el.cloneNode(true);
    el.after(clone);
    hydrateSketchBlocks?.();
    afterEditorCommand();
  }
  function removeBlock(el){
    if(!el)return;
    el.remove();
    afterEditorCommand();
  }
  function editImageElement(imgEl){
    if(!imgEl)return;
    openQuickSheet({
      title:'Replace Image',
      subtitle:'Update the image source without leaving the note.',
      submitLabel:'Save',
      fields:[{id:'url',label:'Image Source',value:imgEl.getAttribute('src')||'',placeholder:'https://example.com/image.png'}],
      onSubmit:async({url})=>{
        if(!url)return;
        imgEl.setAttribute('src',url);
        afterEditorCommand();
      }
    });
  }
  function editImageMetadata(imgEl){
    if(!imgEl)return;
    openQuickSheet({
      title:'Image Metadata',
      subtitle:'Set alt text and title for accessibility and search.',
      submitLabel:'Save',
      fields:[
        {id:'alt',label:'Alt Text',value:imgEl.getAttribute('alt')||'',placeholder:'Describe the image'},
        {id:'title',label:'Title',value:imgEl.getAttribute('title')||'',placeholder:'Optional title'}
      ],
      onSubmit:async({alt,title})=>{
        imgEl.setAttribute('alt',alt||'');
        imgEl.setAttribute('title',title||'');
        afterEditorCommand();
      }
    });
  }
  function editLinkElement(linkEl){
    if(!linkEl)return;
    openQuickSheet({
      title:'Edit Link',
      subtitle:'Update the link label or destination.',
      submitLabel:'Save',
      fields:[
        {id:'label',label:'Label',value:linkEl.textContent||'Link'},
        {id:'url',label:'URL',value:linkEl.getAttribute('href')||'https://'}
      ],
      onSubmit:async({label,url})=>{
        if(!url)return;
        linkEl.setAttribute('href',url);
        linkEl.textContent=label||url;
        afterEditorCommand();
      }
    });
  }
  function highlightSelection(){
    if(!wrapSelectionWithStyle('mark',{backgroundColor:'#fff2a8',color:'inherit',padding:'0 0.08em',borderRadius:'0.25em'})){
      showNotif('Select text first');
      return;
    }
    afterEditorCommand();
  }
  function resolveLegacyAction(name){
    if(typeof name!=='string')return null;
    return name.split('.').reduce((acc,key)=>acc?.[key],window);
  }

  const engine=window.ContextMenuEngine={
    state:{open:false,context:null,items:[],filtered:[],selected:0,submenuItems:[],submenuSelected:0,query:'',anchor:{x:0,y:0},longPressTimer:null},
    MenuRegistry:{
      providers:new Map(),
      pluginActions:[],
      registerProvider(id,provider){ this.providers.set(id,{id,...provider}); },
      registerAction(config){ this.pluginActions.push(config); }
    },
    ContextResolver:{
      matchesTarget(target,context){
        if(!target || target==='*')return true;
        if(Array.isArray(target))return target.some(value=>this.matchesTarget(value,context));
        if(target==='block')return !!context.blockEl;
        if(target==='selection')return context.kinds.has('selection');
        return context.kinds.has(target);
      },
      resolve(target,event,overrides){
        overrides=overrides||{};
        const el=getTargetElement(target);
        const selection=safeText(window.getSelection?.().toString());
        const context={
          event:event||{},
          target:el,
          x:overrides.x ?? event?.clientX ?? 0,
          y:overrides.y ?? event?.clientY ?? 0,
          pointerType:overrides.pointerType || event?.pointerType || (overrides.touch?'touch':'mouse'),
          kinds:new Set(),
          selectionText:selection,
          noteItem:el?.closest?.('[data-note-id]')||null,
          folderItem:el?.closest?.('[data-folder-name]')||null,
          tableCell:el?.closest?.('#editor-content td,#editor-content th')||null,
          tableEl:el?.closest?.('#editor-content table')||null,
          chartEl:el?.closest?.('#editor-content .inline-chart')||null,
          sketchEl:el?.closest?.('#editor-content .note-sketch-block')||null,
          codeEl:el?.closest?.('#editor-content pre') || (el?.closest?.('#editor-content code')?.closest?.('pre,code')) || null,
          imageEl:el?.closest?.('#editor-content img')||null,
          linkEl:el?.closest?.('#editor-content a')||null,
          headingEl:el?.closest?.('#editor-content h1,#editor-content h2,#editor-content h3')||null,
          listItemEl:el?.closest?.('#editor-content li')||null,
          editorRoot:el?.closest?.('#editor-content')||null,
          noteTitleEl:el?.closest?.('#note-title')||null,
          blockEl:getEditorBlock(el),
          noteId:'',
          folderName:''
        };
        if(context.noteItem){ context.kinds.add('note-item'); context.noteId=context.noteItem.dataset.noteId||''; }
        if(context.folderItem){ context.kinds.add('folder-item'); context.folderName=context.folderItem.dataset.folderName||''; }
        if(context.tableEl)context.kinds.add('table-block');
        if(context.chartEl)context.kinds.add('chart-block');
        if(context.sketchEl)context.kinds.add('drawing-block');
        if(context.codeEl)context.kinds.add('code-block');
        if(context.imageEl)context.kinds.add('image-block');
        if(context.linkEl)context.kinds.add('link');
        if(context.headingEl)context.kinds.add('heading-block');
        if(context.listItemEl)context.kinds.add('list-block');
        if(context.editorRoot || context.noteTitleEl)context.kinds.add('editor');
        if(context.noteTitleEl)context.kinds.add('note-title');
        if(selection)context.kinds.add('selection');
        if(context.blockEl && !context.tableEl && !context.chartEl && !context.sketchEl && !context.codeEl && !context.imageEl)context.kinds.add('text-block');
        if((context.editorRoot || context.noteTitleEl) && !context.headingEl && !context.listItemEl && !context.imageEl && !context.tableEl && !context.chartEl && !context.sketchEl && !context.codeEl && !selection)context.kinds.add('note-background');
        if(overrides.manual)context.kinds.add('manual');
        if(!context.kinds.size)context.kinds.add('app-background');
        return context;
      }
    },
    MenuRenderer:{
      filter(items,query){
        const q=safeText(query).toLowerCase();
        if(!q)return items;
        return items.flatMap(item=>{
          if(item==='sep')return [];
          const kids=Array.isArray(item.children)?this.filter(item.children,q):null;
          const hit=item.label.toLowerCase().includes(q) || (item.keywords||'').includes(q);
          if(hit || (kids && kids.length))return [{...item,children:kids}];
          return [];
        });
      },
      compact(items){
        const out=[];
        items.forEach(item=>{
          if(item==='sep'){
            if(!out.length || out[out.length-1]==='sep')return;
            out.push(item);
            return;
          }
          out.push(item);
        });
        if(out[out.length-1]==='sep')out.pop();
        return out;
      },
      renderItem(item,index,isSubmenu){
        if(item==='sep')return '<div class="context-menu-sep"></div>';
        const active=isSubmenu ? index===engine.state.submenuSelected : index===engine.state.selected;
        const hasChildren=Array.isArray(item.children)&&item.children.length;
        return `<button class="context-menu-item${active?' active':''}" type="button" data-menu-index="${index}" ${item.disabled?'disabled':''} aria-haspopup="${hasChildren?'menu':'false'}"><span class="context-menu-item-left">${iconSvg(item.icon,'context-menu-icon')}<span class="context-menu-label">${esc(item.label)}</span></span><span class="context-menu-item-right">${item.hint?`<span class="context-menu-hint">${esc(item.hint)}</span>`:''}${hasChildren?'<span class="context-menu-chevron">›</span>':''}</span></button>`;
      },
      render(){
        const menu=document.getElementById('context-menu');
        const filtered=this.compact(this.filter(engine.state.items,engine.state.query));
        engine.state.filtered=filtered;
        if(engine.state.selected>=filtered.length)engine.state.selected=0;
        const active=filtered[engine.state.selected]||null;
        const submenu=active?.children?this.compact(active.children):[];
        engine.state.submenuItems=submenu;
        if(engine.state.submenuSelected>=submenu.length)engine.state.submenuSelected=0;
        const kinds=engine.state.context?.kinds||new Set();
        const title=kinds.has('drawing-block')?'Drawing Block':kinds.has('image-block')?'Image Block':kinds.has('table-block')?'Table':kinds.has('chart-block')?'Chart':kinds.has('code-block')?'Code Block':kinds.has('note-item')?'Note':kinds.has('folder-item')?'Folder':kinds.has('note-background')?'Note Surface':'Context';
        menu.innerHTML=`<div class="context-menu-shell" role="dialog" aria-label="Context menu"><div class="context-menu-head">${esc(title)}</div><div class="context-menu-search">${iconSvg('search','context-menu-icon')}<input id="context-menu-search" type="text" placeholder="Filter actions" value="${esc(engine.state.query)}" aria-label="Filter context menu actions"></div><div class="context-menu-panel">${filtered.length?`<div class="context-menu-list" role="menu">${filtered.map((item,index)=>this.renderItem(item,index,false)).join('')}</div>`:'<div class="context-menu-empty">No contextual actions here yet.</div>'}${submenu.length?`<div class="context-menu-submenu" role="menu">${submenu.map((item,index)=>this.renderItem(item,index,true)).join('')}</div>`:''}</div></div>`;
        menu.classList.add('open');
        menu.style.left=engine.state.anchor.x+'px';
        menu.style.top=engine.state.anchor.y+'px';
        const rect=menu.getBoundingClientRect();
        if(rect.right>window.innerWidth-8)menu.style.left=(window.innerWidth-rect.width-8)+'px';
        if(rect.bottom>window.innerHeight-8)menu.style.top=(window.innerHeight-rect.height-8)+'px';
        const search=menu.querySelector('#context-menu-search');
        search.addEventListener('input',event=>{
          engine.state.query=event.target.value||'';
          engine.state.selected=0;
          engine.state.submenuSelected=0;
          engine.MenuRenderer.render();
        });
        search.focus({preventScroll:true});
        menu.querySelectorAll('.context-menu-list > .context-menu-item').forEach(btn=>{
          btn.addEventListener('mouseenter',()=>{
            engine.state.selected=parseInt(btn.dataset.menuIndex,10)||0;
            engine.state.submenuSelected=0;
            engine.MenuRenderer.render();
          });
          btn.addEventListener('click',()=>{
            const item=engine.state.filtered[parseInt(btn.dataset.menuIndex,10)||0];
            if(item?.children?.length){
              engine.state.submenuSelected=0;
              engine.MenuRenderer.render();
              return;
            }
            engine.dispatch(item);
          });
        });
        menu.querySelectorAll('.context-menu-submenu .context-menu-item').forEach(btn=>{
          btn.addEventListener('mouseenter',()=>{ engine.state.submenuSelected=parseInt(btn.dataset.menuIndex,10)||0; });
          btn.addEventListener('click',()=>engine.dispatch(engine.state.submenuItems[parseInt(btn.dataset.menuIndex,10)||0]));
        });
        menu.onkeydown=event=>engine.handleKeydown(event);
      }
    },
    collectActions(context){
      const actions=[];
      const providers=[...this.MenuRegistry.providers.values()].sort((a,b)=>(b.priority||0)-(a.priority||0));
      providers.forEach(provider=>{
        if(provider.matches && !provider.matches(context))return;
        const next=provider.getActions?.(context)||[];
        if(next.length)actions.push(...next);
      });
      this.MenuRegistry.pluginActions.forEach(config=>{
        if(!this.ContextResolver.matchesTarget(config.target,context))return;
        if(typeof config.when==='function' && !config.when(context))return;
        actions.push(makeAction(config.label,{id:config.id,icon:config.icon||'sparkles',keywords:config.keywords||[],run:ctx=>config.action?.(ctx)}));
      });
      return this.MenuRenderer.compact(actions);
    },
    dispatch(item){
      if(!item || item.disabled)return;
      contextMenuState=engine.state.context;
      const result=item.run?.(engine.state.context);
      if(result && typeof result.then==='function'){
        result.finally(()=>engine.hide());
      }else{
        engine.hide();
      }
    },
    openAt(x,y,context,items){
      contextMenuState=context;
      this.state.open=true;
      this.state.context=context;
      this.state.items=items;
      this.state.filtered=[];
      this.state.query='';
      this.state.selected=0;
      this.state.submenuItems=[];
      this.state.submenuSelected=0;
      this.state.anchor={x,y};
      this.MenuRenderer.render();
    },
    openManual(x,y,items,state){
      const context={...(state||{}),kinds:new Set(['manual']),x,y};
      const normalized=(items||[]).map(item=>{
        if(item==='sep')return item;
        const fn=resolveLegacyAction(item.actionName);
        return makeAction(item.label,{id:'manual-'+(item.actionName||item.label),icon:item.icon||'document',hint:item.hint||'',run:()=>fn?.()});
      });
      this.openAt(x,y,context,normalized);
    },
    openFromEvent(event){
      const context=this.ContextResolver.resolve(event.target,event);
      const items=this.collectActions(context);
      if(!items.length)return;
      event.preventDefault?.();
      this.openAt(context.x,context.y,context,items);
    },
    hide(){
      const menu=document.getElementById('context-menu');
      menu.classList.remove('open');
      menu.innerHTML='';
      this.state.open=false;
      this.state.context=null;
      this.state.items=[];
      this.state.filtered=[];
      this.state.submenuItems=[];
      contextMenuState=null;
    },
    handleKeydown(event){
      if(!this.state.open)return;
      const top=this.state.filtered;
      const sub=this.state.submenuItems;
      if(event.key==='Escape'){ event.preventDefault(); this.hide(); return; }
      if(event.key==='Tab'){
        const menu=document.getElementById('context-menu');
        const focusables=[...menu.querySelectorAll('#context-menu-search,.context-menu-item:not([disabled])')];
        if(!focusables.length)return;
        event.preventDefault();
        const currentIndex=Math.max(0,focusables.indexOf(document.activeElement));
        const nextIndex=(currentIndex + (event.shiftKey?-1:1) + focusables.length) % focusables.length;
        focusables[nextIndex].focus();
        return;
      }
      if(event.key==='ArrowDown'){ event.preventDefault(); if(sub.length)this.state.submenuSelected=(this.state.submenuSelected+1)%sub.length; else this.state.selected=(this.state.selected+1)%Math.max(top.length,1); this.MenuRenderer.render(); return; }
      if(event.key==='ArrowUp'){ event.preventDefault(); if(sub.length)this.state.submenuSelected=(this.state.submenuSelected-1+sub.length)%sub.length; else this.state.selected=(this.state.selected-1+top.length)%Math.max(top.length,1); this.MenuRenderer.render(); return; }
      if(event.key==='ArrowRight'){ const active=top[this.state.selected]; if(active?.children?.length){ event.preventDefault(); this.state.submenuSelected=0; this.MenuRenderer.render(); } return; }
      if(event.key==='ArrowLeft' && sub.length){ event.preventDefault(); this.state.submenuItems=[]; this.MenuRenderer.render(); return; }
      if(event.key==='Enter' || event.key===' '){ event.preventDefault(); const item=sub.length?sub[this.state.submenuSelected]:top[this.state.selected]; if(item?.children?.length && !sub.length){ this.MenuRenderer.render(); return; } this.dispatch(item); }
    },
    startLongPress(event){
      if(event.touches?.length!==1)return;
      if(event.target?.closest?.('#painter-view,#mindmap-view,#quick-sheet,.color-popover,#search-panel input'))return;
      const touch=event.touches[0];
      clearTimeout(this.state.longPressTimer);
      this.state.longPressTimer=setTimeout(()=>{
        this.openFromEvent({target:event.target,clientX:touch.clientX,clientY:touch.clientY,pointerType:'touch',preventDefault(){}});
      },520);
    },
    cancelLongPress(){
      clearTimeout(this.state.longPressTimer);
      this.state.longPressTimer=null;
    },
    init(){
      if(contextMenuBound)return;
      contextMenuBound=true;
      window.addEventListener('contextmenu',event=>this.openFromEvent(event),true);
      document.addEventListener('click',event=>{ if(!event.target.closest?.('#context-menu')) this.hide(); });
      window.addEventListener('blur',()=>this.hide());
      document.addEventListener('keydown',event=>{
        if(event.key==='ContextMenu' || (event.shiftKey && event.key==='F10')){
          const target=document.activeElement||document.body;
          const rect=target.getBoundingClientRect?.()||{left:window.innerWidth/2,top:window.innerHeight/2,height:0};
          event.preventDefault();
          this.openFromEvent({target,clientX:rect.left+12,clientY:rect.top+Math.max(18,rect.height/2),pointerType:'keyboard',preventDefault(){}});
          return;
        }
        if(this.state.open)this.handleKeydown(event);
      });
      document.addEventListener('touchstart',event=>this.startLongPress(event),{passive:true});
      document.addEventListener('touchmove',()=>this.cancelLongPress(),{passive:true});
      document.addEventListener('touchend',()=>this.cancelLongPress(),{passive:true});
      document.addEventListener('touchcancel',()=>this.cancelLongPress(),{passive:true});
    }
  };

  const registerContextMenu=window.registerContextMenu=function(id,provider){ engine.MenuRegistry.registerProvider(id,provider); };
  const registerContextAction=window.registerContextAction=function(config){ engine.MenuRegistry.registerAction(config); };

  Object.assign(window.contextActions,{
    duplicateBlockFromMenu:()=>{ if(contextMenuState?.blockEl)duplicateBlock(contextMenuState.blockEl); hideContextMenu(); },
    removeBlockFromMenu:()=>{ if(contextMenuState?.blockEl)removeBlock(contextMenuState.blockEl); hideContextMenu(); },
    replaceImageFromMenu:()=>{ if(contextMenuState?.imageEl)editImageElement(contextMenuState.imageEl); hideContextMenu(); },
    editImageMetadataFromMenu:()=>{ if(contextMenuState?.imageEl)editImageMetadata(contextMenuState.imageEl); hideContextMenu(); },
    editLinkFromMenu:()=>{ if(contextMenuState?.linkEl)editLinkElement(contextMenuState.linkEl); hideContextMenu(); }
  });

  registerContextMenu('note-item',{priority:120,matches:ctx=>ctx.kinds.has('note-item'),getActions:ctx=>[
    makeAction('Open Note',{icon:'note',hint:'Enter',run:()=>openNote(ctx.noteId)}),
    makeAction('Rename Note',{icon:'edit',hint:'F2',run:()=>renameNotePrompt(ctx.noteId)}),
    makeAction('Duplicate Note',{icon:'copy',run:()=>duplicateNote(ctx.noteId)}),
    makeAction(bookmarkedNoteIds.has(ctx.noteId)?'Remove Bookmark':'Bookmark Note',{icon:'bookmark',run:()=>toggleBookmarkForNote(ctx.noteId)}),
    'sep',
    makeAction('Delete Note',{icon:'trash',hint:'Del',run:async()=>{ if(currentNote?.id!==ctx.noteId)await openNote(ctx.noteId); await deleteCurrentNote(); }})
  ]});
  registerContextMenu('folder-item',{priority:118,matches:ctx=>ctx.kinds.has('folder-item'),getActions:ctx=>[
    makeAction('Open Folder',{icon:'folder2',run:()=>filterByFolder(ctx.folderName)}),
    makeAction('Rename Folder',{icon:'edit',run:()=>renameFolderPrompt(ctx.folderName)}),
    makeAction('Delete Folder',{icon:'trash',run:()=>deleteFolderPrompt(ctx.folderName)})
  ]});
  registerContextMenu('drawing-block',{priority:112,matches:ctx=>ctx.kinds.has('drawing-block'),getActions:ctx=>[
    makeAction('Edit Drawing',{icon:'edit',run:()=>editSketchBlock(ctx.sketchEl?.dataset?.sketchBlockId)}),
    makeAction('Duplicate Drawing',{icon:'copy',run:()=>duplicateSketchBlock(ctx.sketchEl?.dataset?.sketchBlockId)}),
    makeAction('Export PNG',{icon:'download',run:()=>downloadHref(buildSketchPreview(parseSketchBlockDoc(ctx.sketchEl)),'sketch.png')}),
    makeAction(ctx.sketchEl?.dataset?.resizeLocked==='true'?'Unlock Resize':'Lock Resize',{icon:'move',run:()=>{ ctx.sketchEl.dataset.resizeLocked=ctx.sketchEl.dataset.resizeLocked==='true'?'false':'true'; ctx.sketchEl.style.resize=ctx.sketchEl.dataset.resizeLocked==='true'?'none':'both'; debounceSave(); }}),
    'sep',
    makeAction('Move Up',{icon:'move',run:()=>moveSketchBlock(ctx.sketchEl?.dataset?.sketchBlockId,-1)}),
    makeAction('Move Down',{icon:'move',run:()=>moveSketchBlock(ctx.sketchEl?.dataset?.sketchBlockId,1)}),
    makeAction('Delete Drawing',{icon:'trash',run:()=>deleteSketchBlock(ctx.sketchEl?.dataset?.sketchBlockId)})
  ]});
  registerContextMenu('image-block',{priority:110,matches:ctx=>ctx.kinds.has('image-block'),getActions:ctx=>[
    makeAction('Replace Image',{icon:'upload',run:()=>editImageElement(ctx.imageEl)}),
    makeAction('Image Metadata',{icon:'edit',run:()=>editImageMetadata(ctx.imageEl)}),
    makeAction('Copy Image Source',{icon:'copy',run:async()=>{ const src=ctx.imageEl?.getAttribute('src')||''; if(src)await navigator.clipboard.writeText(src); }}),
    makeAction('Download Image',{icon:'download',run:()=>downloadHref(ctx.imageEl?.getAttribute('src')||'','image')}),
    'sep',
    makeAction('Duplicate Block',{icon:'copy',run:()=>duplicateBlock(ctx.blockEl||ctx.imageEl)}),
    makeAction('Delete Block',{icon:'trash',run:()=>removeBlock(ctx.blockEl||ctx.imageEl)})
  ]});
  registerContextMenu('link',{priority:108,matches:ctx=>ctx.kinds.has('link'),getActions:ctx=>[
    makeAction('Open Link',{icon:'link2',run:()=>window.open(ctx.linkEl?.getAttribute('href')||'','_blank','noopener')}),
    makeAction('Copy Link',{icon:'copy',run:async()=>{ const href=ctx.linkEl?.getAttribute('href')||''; if(href)await navigator.clipboard.writeText(href); }}),
    makeAction('Edit Link',{icon:'edit',run:()=>editLinkElement(ctx.linkEl)}),
    makeAction('Remove Link',{icon:'trash',run:()=>{ ctx.linkEl.outerHTML=esc(ctx.linkEl.textContent||ctx.linkEl.getAttribute('href')||'Link'); afterEditorCommand(); }})
  ]});
  registerContextMenu('table-block',{priority:106,matches:ctx=>ctx.kinds.has('table-block'),getActions:ctx=>{
    contextMenuState=ctx;
    _activeTableCell=ctx.tableCell;
    return [
      makeAction('Row Above',{icon:'table',run:()=>tableAddRowAbove()}),
      makeAction('Row Below',{icon:'table',run:()=>tableAddRowBelow()}),
      makeAction('Column Left',{icon:'table',run:()=>tableAddColLeft()}),
      makeAction('Column Right',{icon:'table',run:()=>tableAddColRight()}),
      'sep',
      makeAction('Delete Row',{icon:'trash',run:()=>tableDeleteRow()}),
      makeAction('Delete Column',{icon:'trash',run:()=>tableDeleteCol()}),
      makeAction('Toggle Header Row',{icon:'table',run:()=>toggleTableHeaderRow()}),
      makeAction('Delete Table',{icon:'trash',run:()=>deleteCurrentTable()})
    ];
  }});
  registerContextMenu('chart-block',{priority:104,matches:ctx=>ctx.kinds.has('chart-block'),getActions:ctx=>[
    makeAction('Edit Chart',{icon:'edit',run:()=>{ contextMenuState=ctx; editCurrentChart(); }}),
    makeAction('Duplicate Chart',{icon:'copy',run:()=>duplicateBlock(ctx.blockEl||ctx.chartEl)}),
    makeAction('Chart to Text',{icon:'quote',run:()=>{ contextMenuState=ctx; chartToTextBlock(); }}),
    makeAction('Delete Chart',{icon:'trash',run:()=>removeBlock(ctx.blockEl||ctx.chartEl)})
  ]});
  registerContextMenu('code-block',{priority:102,matches:ctx=>ctx.kinds.has('code-block'),getActions:ctx=>[
    makeAction('Copy Code',{icon:'copy',run:()=>{ contextMenuState=ctx; copyCodeBlock(); }}),
    makeAction('Duplicate Block',{icon:'copy',run:()=>duplicateBlock(ctx.blockEl||ctx.codeEl)}),
    makeAction('Turn Into Text',{icon:'quote',run:()=>{ contextMenuState=ctx; flattenCodeBlock(); }}),
    makeAction('Delete Block',{icon:'trash',run:()=>removeBlock(ctx.blockEl||ctx.codeEl)})
  ]});
  registerContextMenu('selection',{priority:98,matches:ctx=>ctx.kinds.has('selection') && ctx.kinds.has('editor'),getActions:()=>[
    makeAction('Cut',{icon:'scissors',hint:'Ctrl+X',run:()=>window.contextActions.cutSelection()}),
    makeAction('Copy',{icon:'copy',hint:'Ctrl+C',run:()=>window.contextActions.copySelection()}),
    makeAction('Paste',{icon:'paste',hint:'Ctrl+V',run:()=>window.contextActions.pasteSelection()}),
    'sep',
    makeAction('Bold',{icon:'edit',run:()=>window.contextActions.boldSelection()}),
    makeAction('Italic',{icon:'edit',run:()=>window.contextActions.italicSelection()}),
    makeAction('Highlight',{icon:'highlight',run:()=>highlightSelection()}),
    makeAction('Convert',{icon:'sparkles',children:[
      makeAction('To Table',{icon:'table',run:()=>convertSelectionToTable()}),
      makeAction('To Checklist',{icon:'checklist',run:()=>convertSelectionToChecklist()}),
      makeAction('To Callout',{icon:'quote',run:()=>convertSelectionToCallout()})
    ]})
  ]});
  registerContextMenu('text-block',{priority:96,matches:ctx=>ctx.kinds.has('text-block') || ctx.kinds.has('note-title'),getActions:()=>[
    makeAction('Undo',{icon:'undo',hint:'Ctrl+Z',run:()=>fmt('undo')}),
    makeAction('Redo',{icon:'redo',hint:'Ctrl+Y',run:()=>fmt('redo')}),
    makeAction('Insert Link',{icon:'link2',run:()=>insertLink()}),
    makeAction('Block Quote',{icon:'quote',run:()=>insertBlockquote()}),
    makeAction('Code Block',{icon:'code',run:()=>insertCodeBlock()}),
    makeAction('Find & Replace',{icon:'search',run:()=>openFindReplace()})
  ]});
  registerContextMenu('note-background',{priority:94,matches:ctx=>ctx.kinds.has('note-background'),getActions:()=>[
    makeAction('Insert',{icon:'sparkles',children:[
      makeAction('Drawing',{icon:'image',run:()=>insertSketchBlock()}),
      makeAction('Table',{icon:'table',run:()=>insertTable()}),
      makeAction('Image',{icon:'image',run:()=>insertImage()}),
      makeAction('Checklist',{icon:'checklist',run:()=>insertChecklist()}),
      makeAction('Code Block',{icon:'code',run:()=>insertCodeBlock()}),
      makeAction('Divider',{icon:'quote',run:()=>insertDivider()})
    ]}),
    makeAction('Paste',{icon:'paste',run:()=>window.contextActions.pasteSelection()}),
    makeAction('Quick Capture',{icon:'note',run:()=>openQuickCapture()}),
    makeAction('Save as Template',{icon:'bookmark',run:()=>saveAsTemplate()})
  ]});
  registerContextMenu('app-background',{priority:80,matches:ctx=>ctx.kinds.has('app-background'),getActions:()=>[
    makeAction('New Note',{icon:'note',run:()=>createNote()}),
    makeAction('New Folder',{icon:'folder2',run:()=>createFolderPrompt()}),
    makeAction('Quick Capture',{icon:'note',run:()=>openQuickCapture()}),
    makeAction('Command Palette',{icon:'search',run:()=>openCmdPalette()}),
    makeAction('Settings',{icon:'settings',run:()=>openSettings()})
  ]});
  registerContextAction({
    id:'plugin-ai-improve-writing',
    target:['selection','text-block'],
    label:'AI Improve Writing',
    icon:'sparkles',
    keywords:['ai rewrite improve writing'],
    action:async(context)=>{
      const text=safeText(context.selectionText || context.blockEl?.textContent);
      if(!text){ showNotif('Select text first'); return; }
      await duckCopyPrompt(duckComposePrompt(`Improve the writing below while keeping the meaning.\n\n${text}`),'Prompt copied for AI rewrite');
    }
  });

  // The first engine pass re-rendered the menu on hover and bound click listeners
  // directly to transient button nodes. That made actions unreliable because hover
  // could replace the clicked node before its handler fired. We override the
  // renderer here to use delegated events on the stable menu root instead.
  engine.MenuRenderer.renderItem=function renderItem(item,index,isSubmenu){
    if(item==='sep')return '<div class="context-menu-sep"></div>';
    const active=isSubmenu ? index===engine.state.submenuSelected : index===engine.state.selected;
    const hasChildren=Array.isArray(item.children)&&item.children.length;
    return `<button class="context-menu-item${active?' active':''}" type="button" data-menu-index="${index}" data-menu-level="${isSubmenu?'sub':'top'}" ${item.disabled?'disabled':''} aria-haspopup="${hasChildren?'menu':'false'}"><span class="context-menu-item-left">${iconSvg(item.icon,'context-menu-icon')}<span class="context-menu-label">${esc(item.label)}</span></span><span class="context-menu-item-right">${item.hint?`<span class="context-menu-hint">${esc(item.hint)}</span>`:''}${hasChildren?'<span class="context-menu-chevron">›</span>':''}</span></button>`;
  };
  engine.MenuRenderer.render=function render(){
    const menu=document.getElementById('context-menu');
    const filtered=this.compact(this.filter(engine.state.items,engine.state.query));
    engine.state.filtered=filtered;
    if(engine.state.selected>=filtered.length)engine.state.selected=0;
    const active=filtered[engine.state.selected]||null;
    const submenu=active?.children?this.compact(active.children):[];
    engine.state.submenuItems=submenu;
    if(engine.state.submenuSelected>=submenu.length)engine.state.submenuSelected=0;
    const kinds=engine.state.context?.kinds||new Set();
    const title=kinds.has('drawing-block')?'Drawing Block':kinds.has('image-block')?'Image Block':kinds.has('table-block')?'Table':kinds.has('chart-block')?'Chart':kinds.has('code-block')?'Code Block':kinds.has('note-item')?'Note':kinds.has('folder-item')?'Folder':kinds.has('note-background')?'Note Surface':'Context';
    menu.innerHTML=`<div class="context-menu-shell" role="dialog" aria-label="Context menu"><div class="context-menu-head">${esc(title)}</div><div class="context-menu-search">${iconSvg('search','context-menu-icon')}<input id="context-menu-search" type="text" placeholder="Filter actions" value="${esc(engine.state.query)}" aria-label="Filter context menu actions"></div><div class="context-menu-panel">${filtered.length?`<div class="context-menu-list" role="menu">${filtered.map((item,index)=>this.renderItem(item,index,false)).join('')}</div>`:'<div class="context-menu-empty">No contextual actions here yet.</div>'}${submenu.length?`<div class="context-menu-submenu" role="menu">${submenu.map((item,index)=>this.renderItem(item,index,true)).join('')}</div>`:''}</div></div>`;
    menu.classList.add('open');
    menu.style.left=engine.state.anchor.x+'px';
    menu.style.top=engine.state.anchor.y+'px';
    const rect=menu.getBoundingClientRect();
    if(rect.right>window.innerWidth-8)menu.style.left=(window.innerWidth-rect.width-8)+'px';
    if(rect.bottom>window.innerHeight-8)menu.style.top=(window.innerHeight-rect.height-8)+'px';
    const search=menu.querySelector('#context-menu-search');
    search.addEventListener('input',event=>{
      engine.state.query=event.target.value||'';
      engine.state.selected=0;
      engine.state.submenuSelected=0;
      engine.MenuRenderer.render();
    });
    search.addEventListener('keydown',event=>event.stopPropagation());
    search.focus({preventScroll:true});
    menu.onmouseover=event=>{
      const btn=event.target.closest?.('.context-menu-item');
      if(!btn || !menu.contains(btn) || btn.disabled)return;
      const index=parseInt(btn.dataset.menuIndex,10)||0;
      if(btn.dataset.menuLevel==='sub'){
        engine.state.submenuSelected=index;
        return;
      }
      if(engine.state.selected===index && engine.state.submenuItems.length===((engine.state.filtered[index]?.children||[]).length||0))return;
      engine.state.selected=index;
      engine.state.submenuSelected=0;
      engine.MenuRenderer.render();
    };
    menu.onfocusin=event=>{
      const btn=event.target.closest?.('.context-menu-item');
      if(!btn || !menu.contains(btn) || btn.disabled)return;
      const index=parseInt(btn.dataset.menuIndex,10)||0;
      if(btn.dataset.menuLevel==='sub'){
        engine.state.submenuSelected=index;
        return;
      }
      engine.state.selected=index;
      engine.state.submenuSelected=0;
      engine.MenuRenderer.render();
    };
    menu.onclick=event=>{
      const btn=event.target.closest?.('.context-menu-item');
      if(!btn || !menu.contains(btn) || btn.disabled)return;
      const index=parseInt(btn.dataset.menuIndex,10)||0;
      if(btn.dataset.menuLevel==='sub'){
        engine.dispatch(engine.state.submenuItems[index]);
        return;
      }
      const item=engine.state.filtered[index];
      if(item?.children?.length){
        engine.state.selected=index;
        engine.state.submenuSelected=0;
        engine.MenuRenderer.render();
        return;
      }
      engine.dispatch(item);
    };
    menu.onkeydown=event=>engine.handleKeydown(event);
  };
  engine.dispatch=function dispatch(item){
    if(!item || item.disabled)return;
    contextMenuState=engine.state.context;
    let result;
    try{
      result=item.run?.(engine.state.context);
    }catch(error){
      console.error('Context menu action failed',item?.id,error);
      showNotif('That context action failed.');
      engine.hide();
      return;
    }
    if(result && typeof result.then==='function'){
      result
        .catch(error=>{
          console.error('Context menu action failed',item?.id,error);
          showNotif('That context action failed.');
        })
        .finally(()=>engine.hide());
    }else{
      engine.hide();
    }
  };

  setupCustomContextMenu=function(){ engine.init(); };
  showContextMenu=function(x,y,items,state){ engine.openManual(x,y,items,state); };
  hideContextMenu=function(){ engine.hide(); };
  handleContextMenu=function(event){ engine.openFromEvent(event); };
})();
