const $ = id => document.getElementById(id);
let current = null, names = {}, busy = false, user = null, dirty = false, pollGeneration = 0;
const demo = {demo: true, utterances: [
  {speaker:'A',start:0,end:12000,text:'Welcome back to The Curious Mind. Today we’re talking about something we all want more of: the time and space to do meaningful work.'},
  {speaker:'B',start:12000,end:26000,text:'I love this question, because we often think the answer is to get more done. But sometimes the best thing you can do is decide what deserves your attention in the first place.'},
  {speaker:'A',start:26000,end:34000,text:'So where do you start? Especially when everything on your list feels important.'},
  {speaker:'B',start:34000,end:49000,text:'Start small. Before you open your inbox, write down the one thing that would make today feel worthwhile. Give that thing your first twenty minutes.'},
  {speaker:'A',start:49000,end:59000,text:'I like that. Not a perfect schedule, just a little intention before the day gets away from you.'}
]};
function timestamp(ms){const s=Math.floor(ms/1000);return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;}
function status(message,error=false){$('status').hidden=false;$('status').textContent=message;$('status').classList.toggle('error',error);}
function setBusy(value){busy=value;$('submit').disabled=value;$('demo').disabled=value;$('submit').textContent=value?'Processing…':'Transcribe ↗';}
function renderUtterances(){
  const container=$('utterances');container.replaceChildren();
  const query=$('search').value.toLowerCase();
  const rows=current.utterances.filter(u=>u.text.toLowerCase().includes(query)||(names[u.speaker]||'').toLowerCase().includes(query));
  if(!rows.length){const p=document.createElement('p');p.className='empty';p.textContent=current.utterances.length?'No matching passages.':'No speech segments were detected in this audio.';container.append(p);}
  for(const u of rows){
    const row=document.createElement('article');row.className='utterance';
    const time=document.createElement(current.url?'a':'span');time.className='time';time.textContent=timestamp(u.start);
    if(current.url){time.href=`${current.url}&t=${Math.floor(u.start/1000)}s`;time.target='_blank';time.rel='noopener noreferrer';time.setAttribute('aria-label',`Open video at ${timestamp(u.start)}`);}
    const body=document.createElement('div'),name=document.createElement('span'),text=document.createElement('p');name.className='speaker';name.textContent=names[u.speaker]||`Speaker ${u.speaker}`;text.textContent=u.text;body.append(name,text);row.append(time,body);container.append(row);
  }
}
function show(data){
  current=data;names={...(data.names||{})};dirty=false;$('save-form').hidden=!!data.demo;$('conversation-title').value=data.title||'Your conversation';$('source-url').value=data.url||'';$('save-status').textContent=data.demo?'':'Saved to your private library.';$('result-title').textContent=data.title||'Your conversation, on the page.';$('search').value='';$('results').hidden=false;$('result-kind').textContent=data.demo?'SAMPLE TRANSCRIPT · FICTIONAL CONVERSATION':'YOUR TRANSCRIPT';
  const speakers=[...new Set(data.utterances.map(u=>u.speaker))];$('summary').textContent=`${speakers.length} speakers · ${data.utterances.length} passages${data.demo?' · Demo only':''}`;
  $('speakers').replaceChildren();
  speakers.forEach((speaker,i)=>{const label=document.createElement('label');label.textContent=`Speaker ${speaker}`;const input=document.createElement('input');input.id=`speaker-${i}`;input.maxLength=80;input.value=names[speaker]||'';input.placeholder=`Speaker ${speaker}`;input.addEventListener('input',()=>{names[speaker]=input.value.trim();markDirty();renderUtterances();});label.append(input);$('speakers').append(label);});
  renderUtterances();$('results').scrollIntoView({behavior:'smooth',block:'start'});
}
async function request(url,options){const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'The request could not be processed.');return data;}
async function poll(id, generation = pollGeneration){
  if(generation!==pollGeneration)return;
  const labels={queued:'Your transcript is queued.',downloading:'Getting audio from YouTube…',uploading:'Sending audio for transcription…',transcribing:'Transcribing and separating speakers. Longer podcasts can take several minutes…'};
  try{const job=await request(`/api/transcripts/${id}`);if(generation!==pollGeneration)return;
    if(job.status==='error'){try{localStorage.removeItem('cadence-job-'+user.id);}catch{}throw Error(job.error);}
    if(job.status==='completed'){try{localStorage.removeItem('cadence-job-'+user.id);}catch{}setBusy(false);status('Your transcript is ready. Rename speakers or download a copy below.');show(job);loadHistory();return;}
    status(labels[job.status]||'Processing…');setTimeout(()=>poll(id,generation),3000);
  }catch(error){if(generation!==pollGeneration)return;setBusy(false);status(error.message,true);loadHistory();}
}
$('transcribe-form').addEventListener('submit',async event=>{event.preventDefault();if(busy)return;if(!user){status('Sign in first to save your conversation.',true);$('email').focus();return;}if(!canLeave())return;setBusy(true);$('results').hidden=true;status('Starting your transcript…');try{const job=await request('/api/transcripts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:$('url').value})});try{localStorage.setItem('cadence-job-'+user.id,job.id);}catch{}poll(job.id);}catch(error){setBusy(false);status(error.message,true);}});
$('demo').addEventListener('click',()=>{if(!busy&&canLeave()){$('status').hidden=true;show(demo);}});
$('search').addEventListener('input',renderUtterances);
$('export').addEventListener('click',()=>{if(!current)return;const text=[current.demo?'Cadence — fictional sample transcript':`Transcript: ${current.url}`,'',...current.utterances.map(u=>`[${timestamp(u.start)}] ${names[u.speaker]||`Speaker ${u.speaker}`}\n${u.text}\n`)].join('\n');const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='cadence-transcript.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
request('/api/config').then(config=>{if(!config.configured){$('config').hidden=false;$('config').textContent='Local setup: add your AssemblyAI API key to .env to transcribe real videos. The sample is ready to explore.';}}).catch(()=>status('Cannot reach the server. Restart the app and refresh.',true));

function markDirty(){if(current&&!current.demo){dirty=true;$('save-status').textContent='Unsaved changes — save before leaving.';}}
function canLeave(){return !dirty||confirm('Discard unsaved title or speaker-name changes?');}
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
$('conversation-title').addEventListener('input',markDirty);
$('source-url').addEventListener('input',markDirty);
$('save-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!current||current.demo)return;
  const id=current.id, changes={title:$('conversation-title').value,names:{...names},url:$('source-url').value};
  const snapshot=JSON.stringify(changes);$('save').disabled=true;$('save-status').textContent='Saving…';
  try{await request(`/api/transcripts/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(changes)});
    if(current?.id===id){Object.assign(current,changes);dirty=snapshot!==JSON.stringify({title:$('conversation-title').value,names:{...names},url:$('source-url').value});$('save-status').textContent=dirty?'New changes still need saving.':'Saved to your private library.';$('result-title').textContent=changes.title;renderUtterances();}await loadHistory();
  }catch(error){$('save-status').textContent='Not saved: '+error.message;}finally{$('save').disabled=false;}
});
async function loadHistory(){
  if(!user)return;const owner=user.id;$('library').hidden=false;
  try{const items=await request('/api/transcripts');if(user?.id!==owner)return;$('history').replaceChildren();$('library-status').textContent=items.length?'':'Your next conversation will appear here automatically.';
    for(const item of items){const button=document.createElement('button');button.className='history-item';button.type='button';const title=document.createElement('strong'),detail=document.createElement('span');title.textContent=item.title||'YouTube conversation';detail.textContent=`${new Date(item.created*1000).toLocaleString()} · ${item.status}${item.recovered?' · Recovered':''}`;button.append(title,detail);
      button.addEventListener('click',async()=>{if(!canLeave())return;try{const data=await request('/api/transcripts/'+item.id);if(user?.id!==owner)return;if(data.status==='completed'){show(data);}else if(data.status==='error'){status(data.error,true);}else{setBusy(true);pollGeneration++;poll(data.id);}}catch(error){status(error.message,true);}});$('history').append(button);}
  }catch(error){$('library-status').textContent='Could not load conversations: '+error.message;}
}
async function signedIn(account){user=account;$('account-card').hidden=true;$('account-bar').hidden=false;$('account-email').textContent=account.email;$('password').value='';await loadHistory();try{const saved=localStorage.getItem('cadence-job-'+user.id);if(saved){setBusy(true);poll(saved);}}catch{}}
$('auth-form').addEventListener('submit',async event=>{event.preventDefault();const action=event.submitter?.value||'login';const buttons=[...$('auth-form').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);$('auth-status').textContent='Please wait…';try{const account=await request('/api/auth/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('email').value,password:$('password').value})});$('auth-status').textContent='';await signedIn(account);}catch(error){$('auth-status').textContent=error.message;}finally{buttons.forEach(b=>b.disabled=false);}});
$('logout').addEventListener('click',async()=>{if(!canLeave())return;try{await request('/api/auth/logout',{method:'POST'});pollGeneration++;user=null;current=null;names={};dirty=false;setBusy(false);$('account-card').hidden=false;$('account-bar').hidden=true;$('library').hidden=true;$('history').replaceChildren();$('results').hidden=true;$('status').hidden=true;$('utterances').replaceChildren();$('speakers').replaceChildren();}catch(error){status(error.message,true);}});
$('refresh-library').addEventListener('click',loadHistory);
request('/api/auth/me').then(signedIn).catch(()=>{});
