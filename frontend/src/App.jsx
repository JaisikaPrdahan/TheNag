import { useEffect, useMemo, useState } from 'react'
import { BarChart3, Bell, Brain, BriefcaseBusiness, ChevronDown, CircleCheck, Clock3, Database, Filter, LayoutGrid, Menu, Plus, Search, Settings, ShieldCheck, SlidersHorizontal, Sparkles, Target, TrendingUp, UserRound, X } from 'lucide-react'
import OpportunityCard from './components/OpportunityCard.jsx'
import WhyPanel from './components/WhyPanel.jsx'
import IntakeModal from './components/IntakeModal.jsx'
import { apiFetch } from './api.js'
import DraftPanel from './components/DraftPanel.jsx'

const nav = [
  {id:'feed', label:'For you', icon:Sparkles},
  {id:'saved', label:'Saved', icon:BriefcaseBusiness},
  {id:'reflect', label:'Weekly Reflect', icon:BarChart3},
  {id:'sources', label:'Source trust', icon:ShieldCheck},
]

function Reflect({ data }) {
  return <div className="page-content reflect-page">
    <div className="page-heading"><div><div className="eyebrow"><BarChart3 size={15}/> Weekly Reflect</div><h1>Your attention has a pattern.</h1><p>A weekly read on what you save, skip, and actually act on.</p></div><div className="period"><Clock3 size={15}/> {data.period}</div></div>
    <div className="reflect-hero"><div><span className="kicker">Your week in one sentence</span><h2>You’re finding the right roles.<br/><em>Now make fewer, stronger moves.</em></h2><p>{data.nudge}</p></div><div className="week-score"><span>Follow-through</span><strong>{data.stats.follow_through}</strong><small>accepted ÷ saved</small></div></div>
    <div className="stat-strip">{Object.entries(data.stats).slice(0,3).map(([key,value])=><div key={key}><strong>{value}</strong><span>{key}</span></div>)}</div>
    <div className="reflect-grid"><section className="insight-card"><h3><TrendingUp size={18}/> Patterns TheNag noticed</h3>{data.insights.map((item,i)=><div className="insight-row" key={item}><b>0{i+1}</b><p>{item}</p></div>)}</section>
      <section className="skills-card"><span>Skills appearing most</span><div className="skill-orbit">{data.skills.map((s,i)=><div style={{'--i':i}} key={s}>{s}</div>)}</div><p>These are signals—not a box. One decision never permanently hides a role.</p></section></div>
  </div>
}

function Sources({ sources }) { if (!sources.length) return <div className="page-content sources-page"><div className="empty-state"><ShieldCheck/><h3>No source history yet</h3><p>Sources appear here after you process Reels and act on them.</p></div></div>; return <div className="page-content sources-page"><div className="page-heading"><div><div className="eyebrow"><ShieldCheck size={15}/> Shared source-trust bank</div><h1>Trust built from evidence.</h1><p>Reliability uses repeated observations, never a single unsupported report.</p></div></div><div className="source-table"><div className="source-table-head"><span>Source</span><span>Track record</span><span>Trust</span><span>Assessment</span></div>{sources.map(source=><article key={source.id}><div><div className="source-avatar">{source.name.slice(1,3).toUpperCase()}</div><div><strong>{source.name}</strong><small>{source.observation_count} observations</small></div></div><div className="track-record"><span className="confirmed" style={{width:`${source.confirmed/Math.max(source.observation_count,1)*100}%`}}/><span className="changed" style={{width:`${source.changed/Math.max(source.observation_count,1)*100}%`}}/><span className="misleading" style={{width:`${source.misleading/Math.max(source.observation_count,1)*100}%`}}/></div><div className={`trust-number ${source.trust_score<50?'low':''}`}>{source.trust_score}<small>/100</small></div><div><b>{source.assessment}</b><p>{source.evidence}</p></div></article>)}</div><div className="legend"><span><i className="confirmed"/> Confirmed</span><span><i className="changed"/> Changed</span><span><i className="misleading"/> Misleading or expired</span></div></div> }

function MemoryRail({ memories }) { return <aside className="memory-rail"><div className="rail-title"><Brain size={18}/><div><strong>Your memory</strong><span>Private · learning</span></div><span className="live-dot"/></div><div className="memory-list">{memories.length===0&&<p className="memory-empty">Nothing remembered yet. Save, accept or skip an opportunity and TheNag will learn.</p>}{memories.map((memory,i)=><div className="memory-chip" key={memory.id}><span>{i+1}</span><p>{memory.text}</p></div>)}</div><div className="defense"><ShieldCheck size={18}/><div><b>Memory Defense on</b><p>Emails and phone numbers are redacted before retention.</p></div></div><button className="manage-memory"><Settings size={15}/> Manage memory</button></aside> }

export default function App() {
  const [data,setData] = useState({opportunities:[],sources:[],memories:[],reflect:null,user:{}}); const [draft,setDraft] = useState(null); const [loaded,setLoaded] = useState(false); const [active,setActive] = useState('feed'); const [why,setWhy] = useState(null); const [intake,setIntake] = useState(false); const [query,setQuery] = useState(''); const [category,setCategory] = useState('All'); const [toast,setToast] = useState(''); const [mobileNav,setMobileNav] = useState(false)
  const loadFeed = () => apiFetch('/api/bootstrap').then(api=>setData(current=>({...current,...api,memories:api.memories||[]}))).catch(e=>flash(e.message)).finally(()=>setLoaded(true))
  useEffect(()=>{ loadFeed() },[])
  const opportunities = useMemo(()=>data.opportunities.filter(item => (active!=='saved'||item.status==='saved') && (category==='All'||item.category===category) && `${item.title||''} ${item.company||''} ${item.skills?.join(' ')||''}`.toLowerCase().includes(query.toLowerCase())),[data,active,category,query])
  const flash = msg => { setToast(msg); setTimeout(()=>setToast(''),4000) }
  const patch = (id, fields) => setData(current=>({...current, opportunities:current.opportunities.map(o=>o.id===id?{...o,...fields}:o)}))
  const action = async (item, next) => {
    patch(item.id,{status:next})
    try {
      const result = await apiFetch(`/api/opportunities/${item.id}/action`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:next})})
      if (next==='accepted') { patch(item.id,{confirmation:result.confirmation||[]}); flash((result.confirmation||[]).map(c=>c.label).join(' · ')||'Accepted—nothing was submitted.') }
      else flash(`Marked as ${next}. Memory updated.`)
    } catch (e) {
      patch(item.id,{status:item.status})
      if (e.status===404) { flash('This item no longer exists — refresh'); loadFeed() } else flash(e.message)
    }
  }
  const confirmDate = async item => {
    try {
      const result = await apiFetch(`/api/opportunities/${item.id}/confirm-date`,{method:'POST'})
      patch(item.id,{deadline_confidence:'green',confirmation:result.confirmation||[]}); flash((result.confirmation||[]).map(c=>c.label).join(' · ')||'Date confirmed.')
    } catch (e) { if (e.status===404) { flash('This item no longer exists — refresh'); loadFeed() } else flash(e.message) }
  }
  const processed = item => { setData(current=>({...current,opportunities:[item,...current.opportunities]})); setIntake(false); setWhy(item); flash('Processed with memory and source history.') }
  const reflect = data.reflect || {period:'Last 7 days',stats:{saved:0,accepted:0,skipped:0,follow_through:'0%'},insights:[],skills:[],nudge:''}
  const savedCount = data.opportunities.filter(o=>o.status==='saved').length
  const userName = data.user?.name || 'You'
  return <div className="app-shell">
    <header><button className="mobile-menu" onClick={()=>setMobileNav(!mobileNav)}>{mobileNav?<X/>:<Menu/>}</button><button className="brand" onClick={()=>setActive('feed')}><span className="brand-mark">N</span><span>TheNag<small>opportunity memory</small></span></button><div className="global-search"><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search your opportunities"/><kbd>⌘ K</kbd></div><div className="header-actions"><button><Bell size={18}/><span className="notification-dot"/></button><div className="user-avatar">{userName.slice(0,1).toUpperCase()}</div><div className="user-copy"><b>{userName}</b><span>Job seeker</span></div><ChevronDown size={15}/></div></header>
    <aside className={`sidebar ${mobileNav?'open':''}`}><nav>{nav.map(item=><button key={item.id} className={active===item.id?'active':''} onClick={()=>{setActive(item.id);setMobileNav(false)}}><item.icon size={18}/>{item.label}{item.id==='saved'&&savedCount>0&&<span>{savedCount}</span>}</button>)}</nav><div className="sidebar-bottom"><div className={`mode-card ${data.modes?.memory==='hindsight-cloud'?'live':''}`}><div><Database size={16}/><span>Memory: {data.modes?.memory==='hindsight-cloud'?'Hindsight Cloud':'Demo mode'}</span></div><p>{data.modes?.memory==='hindsight-cloud'?'Retaining and recalling from your real Hindsight bank.':'Hindsight + Groq ready when credentials are added.'}</p></div><button><Settings size={18}/> Settings</button><button><UserRound size={18}/> Profile</button></div></aside>
    <main>
      {active==='reflect'?<Reflect data={reflect}/>:active==='sources'?<Sources sources={data.sources}/>:<div className="feed-layout"><div className="feed-main"><section className="welcome"><div><div className="eyebrow"><Brain size={15}/> Private memory · learns from what you do</div><h1>{active==='saved'?'Worth coming back to.':'Fewer listings. Better fit.'}</h1><p>{active==='saved'?'The opportunities you asked TheNag to remember.':'Because more alerts were never the answer—better memory is.'}</p></div><button className="add-button" onClick={()=>setIntake(true)}><Plus size={18}/> Add opportunity</button></section>
        <div className="feed-controls"><div className="category-tabs">{['All','Jobs & Gigs','Interviews & Hiring Drives'].map(item=><button key={item} className={category===item?'active':''} onClick={()=>setCategory(item)}>{item}</button>)}</div><button className="filter-button"><SlidersHorizontal size={16}/> Filters</button></div>
        <div className="result-copy"><span>{opportunities.length} ranked opportunities</span></div>
        <div className="opportunity-list">{opportunities.map(item=><OpportunityCard key={item.id} item={item} onWhy={setWhy} onAction={action} onDraft={setDraft} onConfirmDate={confirmDate}/>)}</div>
        {opportunities.length===0&&loaded&&(data.opportunities.length===0
          ?<div className="empty-state"><LayoutGrid/><h3>Paste a Reel link to get started</h3><p>Real Reels you process and real actions you take are all that appear here.</p><button className="add-button" onClick={()=>setIntake(true)}><Plus size={18}/> Add opportunity</button></div>
          :<div className="empty-state"><LayoutGrid/><h3>No opportunities match</h3><p>Try another search, tab or filter.</p></div>)}</div><MemoryRail memories={data.memories}/></div>}
    </main>
    {why&&<WhyPanel item={why} onClose={()=>setWhy(null)}/>} {draft&&<DraftPanel item={data.opportunities.find(o=>o.id===draft.id)||draft} onClose={()=>setDraft(null)} onAction={action} onConfirmDate={confirmDate}/>} {intake&&<IntakeModal onClose={()=>setIntake(false)} onProcessed={processed}/>} {toast&&<div className="toast"><CircleCheck size={18}/>{toast}</div>}
  </div>
}
