import html from '../static/index.html?raw';
import app from '../static/app.js?raw';
import productionCss from '../static/style.css?raw';
import dm400 from '@fontsource/dm-sans/files/dm-sans-latin-400-normal.woff2?url';
import dm500 from '@fontsource/dm-sans/files/dm-sans-latin-500-normal.woff2?url';
import dm600 from '@fontsource/dm-sans/files/dm-sans-latin-600-normal.woff2?url';
import dm700 from '@fontsource/dm-sans/files/dm-sans-latin-700-normal.woff2?url';
import man400 from '@fontsource/manrope/files/manrope-latin-400-normal.woff2?url';
import man500 from '@fontsource/manrope/files/manrope-latin-500-normal.woff2?url';
import man600 from '@fontsource/manrope/files/manrope-latin-600-normal.woff2?url';
import man700 from '@fontsource/manrope/files/manrope-latin-700-normal.woff2?url';
import man800 from '@fontsource/manrope/files/manrope-latin-800-normal.woff2?url';

// Same-origin srcdoc isolates the app's globals and document-level handlers per story.
// Import only these three production files: never serve the repository as staticDirs.
const script = value => `<script>${value.replaceAll('</script', '<\\/script')}<\/script>`;
const faces = (family, files) => files.map((file, i) => `@font-face{font-family:'${family}';font-style:normal;font-weight:${400+i*100};font-display:block;src:url('${new URL(file, window.location.href).href}') format('woff2')}`).join('');

function fixture(state) {
  const account = { id: 'fictional-account', email: 'alex@example.com' };
  const transcript = {
    id: 'fictional-conversation', status: 'completed', title: 'Making room for meaningful work',
    url: 'https://www.youtube.com/watch?v=abcdefghijk', created: 1794312000,
    names: { A: 'Alex · Host', B: 'Sam · Guest' },
    utterances: [
      { speaker: 'A', start: 0, end: 12000, text: 'Welcome back. Today we’re exploring how to make time for the conversations and work that matter.' },
      { speaker: 'B', start: 12000, end: 26000, text: 'Start by choosing one thing you want to give your full attention to. A small, deliberate step can change the shape of your day.' },
      { speaker: 'A', start: 26000, end: 34000, text: 'What does that look like when your calendar is already full?' },
      { speaker: 'B', start: 34000, end: 49000, text: 'It can be as simple as twenty minutes without notifications. Give yourself space to think before reacting to everything around you.' },
    ],
  };
  const signedOut = ['signed-out', 'sign-in-error', 'setup'].includes(state);
  const library = state === 'empty-library' ? [] : [transcript];
  const storage = new Map();
  Object.defineProperty(window, 'localStorage', { value: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) } });
  // Fix locale/timezone differences in the production library's date labels.
  Date.prototype.toLocaleString = function () { return '11/10/2026, 12:00:00 PM'; };
  Element.prototype.scrollIntoView = () => {};
  window.fetch = async (url, options = {}) => {
    const path = String(url);
    let status = 200, body;
    if (path === '/api/config') body = { configured: state !== 'setup' };
    else if (path === '/api/auth/me') { status = signedOut ? 401 : 200; body = signedOut ? { detail: 'Please sign in.' } : account; }
    else if (path === '/api/transcripts') body = library;
    else if (path === '/api/transcripts/fictional-conversation') body = options.method === 'PATCH' ? { ok: true } : transcript;
    else { status = 400; body = { detail: 'This is a visual fixture; live API requests are disabled.' }; }
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  };
  window.__fixture = { state, transcript, signedOut };
}

async function initializeState() {
  // Let the real startup /me request and loadHistory settle before changing state.
  for (let i = 0; i < 20; i++) await Promise.resolve();
  const { state, transcript } = window.__fixture;
  if (['transcript', 'search-empty', 'unsaved'].includes(state)) show(transcript);
  if (state === 'search-empty') { $('search').value = 'no matching words'; renderUtterances(); }
  if (state === 'unsaved') { $('conversation-title').value = 'A new title for this conversation'; markDirty(); }
  if (state === 'processing') { setBusy(true); status('Transcribing and separating speakers. Longer podcasts can take several minutes…'); }
  if (state === 'download-error') status('Could not download this video. Try a public, non-live video under 2 hours. YouTube may restrict automated downloads.', true);
  if (state === 'sign-in-error') { $('email').value = 'alex@example.com'; $('auth-status').textContent = 'Email or password is incorrect.'; }
  await document.fonts.ready;
  window.__visualReady = true;
}

function render({ state }) {
  const frame = document.createElement('iframe');
  frame.title = `Cadence visual fixture: ${state}`;
  frame.style.cssText = 'display:block;width:100%;height:1800px;border:0;';
  const css = productionCss.replace(/@import\s+url\([^;]+;/g, '');
  const fonts = faces('DM Sans', [dm400,dm500,dm600,dm700]) + faces('Manrope', [man400,man500,man600,man700,man800]);
  frame.srcdoc = html
    .replace('<link rel="stylesheet" href="/style.css">', `<style>${fonts}${css}</style>`)
    .replace('<script src="/app.js" defer></script>', '')
    .replace('</body>', script(`(${fixture.toString()})(${JSON.stringify(state)});`) + script(app) + script(`(${initializeState.toString()})();`) + '</body>');
  return frame;
}

async function play({ canvasElement }) {
  const frame = canvasElement.querySelector('iframe');
  const deadline = Date.now() + 15000;
  while (!frame.contentWindow?.__visualReady) {
    if (Date.now() > deadline) throw new Error('Cadence fixture did not become ready');
    await new Promise(resolve => setTimeout(resolve, 25));
  }
  // Measure content rather than viewport height, so full-page snapshots include every section.
  frame.style.height = `${Math.ceil(frame.contentDocument.body.getBoundingClientRect().height)}px`;
}

export default { title: 'Cadence/Screens', render, play };
export const SignedOut = { args: { state: 'signed-out' } };
export const SignInError = { args: { state: 'sign-in-error' } };
export const MissingApiKey = { args: { state: 'setup' } };
export const EmptyLibrary = { args: { state: 'empty-library' } };
export const SavedConversations = { args: { state: 'library' } };
export const Transcript = { args: { state: 'transcript' } };
export const NoSearchResults = { args: { state: 'search-empty' } };
export const UnsavedChanges = { args: { state: 'unsaved' } };
export const Processing = { args: { state: 'processing' } };
export const DownloadError = { args: { state: 'download-error' } };
