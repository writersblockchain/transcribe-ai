const $ = id => document.getElementById(id);
let current = null, names = {}, busy = false;
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
  current=data;names={};$('search').value='';$('results').hidden=false;$('result-kind').textContent=data.demo?'SAMPLE TRANSCRIPT · FICTIONAL CONVERSATION':'YOUR TRANSCRIPT';
  const speakers=[...new Set(data.utterances.map(u=>u.speaker))];$('summary').textContent=`${speakers.length} speakers · ${data.utterances.length} passages${data.demo?' · Demo only':''}`;
  $('speakers').replaceChildren();
  speakers.forEach((speaker,i)=>{const label=document.createElement('label');label.textContent=`Speaker ${speaker}`;const input=document.createElement('input');input.id=`speaker-${i}`;input.maxLength=80;input.placeholder=`Speaker ${speaker}`;input.addEventListener('input',()=>{names[speaker]=input.value.trim();renderUtterances();});label.append(input);$('speakers').append(label);});
  renderUtterances();$('results').scrollIntoView({behavior:'smooth',block:'start'});
}
async function request(url,options){const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'The request could not be processed.');return data;}
async function poll(id){
  const labels={queued:'Your transcript is queued.',downloading:'Getting audio from YouTube…',uploading:'Sending audio for transcription…',transcribing:'Transcribing and separating speakers. Longer podcasts can take several minutes…'};
  try{const job=await request(`/api/transcripts/${id}`);
    if(job.status==='error'){try{localStorage.removeItem('cadence-job');}catch{}throw Error(job.error);}
    if(job.status==='completed'){try{localStorage.removeItem('cadence-job');}catch{}setBusy(false);status('Your transcript is ready. Rename speakers or download a copy below.');show(job);return;}
    status(labels[job.status]||'Processing…');setTimeout(()=>poll(id),3000);
  }catch(error){setBusy(false);status(error.message,true);}
}
$('transcribe-form').addEventListener('submit',async event=>{event.preventDefault();if(busy)return;setBusy(true);$('results').hidden=true;status('Starting your transcript…');try{const job=await request('/api/transcripts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:$('url').value})});try{localStorage.setItem('cadence-job',job.id);}catch{}poll(job.id);}catch(error){setBusy(false);status(error.message,true);}});
$('demo').addEventListener('click',()=>{if(!busy){$('status').hidden=true;show(demo);}});
$('search').addEventListener('input',renderUtterances);
$('export').addEventListener('click',()=>{if(!current)return;const text=[current.demo?'Cadence — fictional sample transcript':`Transcript: ${current.url}`,'',...current.utterances.map(u=>`[${timestamp(u.start)}] ${names[u.speaker]||`Speaker ${u.speaker}`}\n${u.text}\n`)].join('\n');const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='cadence-transcript.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
request('/api/config').then(config=>{if(!config.configured){$('config').hidden=false;$('config').textContent='Local setup: add your AssemblyAI API key to .env to transcribe real videos. The sample is ready to explore.';}}).catch(()=>status('Cannot reach the server. Restart the app and refresh.',true));
try{const saved=localStorage.getItem('cadence-job');if(saved){setBusy(true);poll(saved);}}catch{}
