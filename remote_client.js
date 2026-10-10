
const REMOTE_BASE = (typeof window !== 'undefined' && window.location && window.location.host)
  ? `${window.location.protocol}
  : 'http://127.0.0.1:5000';

async function fetchServerData() {
  try {
    const r = await fetch(`${REMOTE_BASE}/data`, {cache: 'no-store'});
    if (!r.ok) throw new Error('HTTP '+r.status);
    const j = await r.json();
    window.realTimeData = j.real_time || {};
    window.historicalData = j.historical || {};
    window.radiationCache = j.radiation_cache || {};
    try{ localStorage.setItem('lipas:data', JSON.stringify(j)); }catch(e){}
    return j;
  } catch (e) {
    console.warn('remote_client: fetchServerData failed', e);
    return null;
  }
}

async function fetchServerStatus() {
  try {
    const r = await fetch(`${REMOTE_BASE}/status`, {cache:'no-store'});
    if (!r.ok) throw new Error('HTTP '+r.status);
    return await r.json();
  } catch (e) {
    console.warn('remote_client: fetchServerStatus failed', e);
    return null;
  }
}

async function serverPredict(input) {
  try {
    const r = await fetch(`${REMOTE_BASE}/predict`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({input})
    });
    if (!r.ok) throw new Error('HTTP '+r.status);
    const j = await r.json();
    if (j && (j.prediction || j.pred)) {
      return Object.assign({}, j, j.prediction || j.pred);
    }
    return j;
  } catch (e) {
    console.warn('remote_client: serverPredict failed', e);
    return null;
  }
}

async function initRemoteClient(){
  try{
    const cached = localStorage.getItem('lipas:data');
    if(cached){
      const j = JSON.parse(cached);
      window.realTimeData = j.real_time || {};
      window.historicalData = j.historical || {};
      window.radiationCache = j.radiation_cache || {};
      console.log('remote_client: hydrated from cache');
    }
  }catch(e){/* ignore cache errors */}

  fetchServerData().catch(()=>{});
  setInterval(fetchServerData, 60000);
  setInterval(fetchServerStatus, 120000);
  window.fetchServerData = fetchServerData;
  window.fetchServerStatus = fetchServerStatus;
  window.serverPredict = serverPredict;
  console.log('remote_client loaded, server base', REMOTE_BASE);
}

initRemoteClient();
