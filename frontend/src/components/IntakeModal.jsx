import { FileVideo, LoaderCircle, Sparkles, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'

export default function IntakeModal({ onClose, onProcessed }) {
  const [tab, setTab] = useState('caption'); const [caption, setCaption] = useState(''); const [source, setSource] = useState(''); const [file, setFile] = useState(null); const [loading, setLoading] = useState(false); const input = useRef()
  const submit = async () => {
    setLoading(true)
    try {
      let response
      if (tab === 'upload' && file) { const body = new FormData(); body.append('file', file); body.append('caption', caption); body.append('source_creator', source); response = await fetch('/api/process-upload', { method:'POST', body }) }
      else response = await fetch('/api/process-caption', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({caption, source_creator:source}) })
      if (!response.ok) throw new Error('API unavailable')
      onProcessed(await response.json())
    } catch { onProcessed({ title:'Frontend Engineer', company:'Demo Company', location:'Bengaluru', work_mode:'Remote', employment_type:'Full-time', skills:['React','TypeScript'], experience:'1–2 years', compensation:'Not provided', deadline:'12 October', source_creator:source || '@newsource', category:'Jobs & Gigs', extraction_confidence:84, source_trust:60, rank:86, status:'new', duplicate:{status:'new',label:'New opportunity',changes:[]}, why:['Remote React work matches your remembered preferences.','This is a new source, so confidence remains cautious.'], recommended_action:'Review and prepare a draft application' }) }
    finally { setLoading(false) }
  }
  return <div className="modal-backdrop"><div className="intake-modal">
    <button className="close-button" onClick={onClose}><X size={20}/></button>
    <div className="eyebrow"><Sparkles size={15}/> Add an opportunity</div><h2>Turn a Reel into a useful decision</h2><p>Paste the caption or upload a video. TheNag extracts the details, checks memory, and prepares a draft-only next step.</p>
    <div className="input-tabs"><button className={tab==='caption'?'active':''} onClick={()=>setTab('caption')}>Paste caption</button><button className={tab==='upload'?'active':''} onClick={()=>setTab('upload')}>Upload video</button></div>
    {tab === 'upload' && <button className="dropzone" onClick={()=>input.current.click()}><input ref={input} hidden type="file" accept="video/*" onChange={e=>setFile(e.target.files[0])}/><FileVideo size={28}/><strong>{file?.name || 'Choose a Reel or video'}</strong><span>MP4, MOV or WebM · Whisper when enabled</span></button>}
    <label>Caption text<textarea value={caption} onChange={e=>setCaption(e.target.value)} placeholder="Example: React developer की भर्ती — remote role, 1–2 years experience, apply by 12 October…"/></label>
    <label>Source creator <input value={source} onChange={e=>setSource(e.target.value)} placeholder="@creator (optional)"/></label>
    <div className="language-note">English · हिन्दी · Hinglish</div>
    <button className="process-button" disabled={loading || (!caption.trim() && !file)} onClick={submit}>{loading?<LoaderCircle className="spin" size={18}/>:<Upload size={18}/>} {loading?'Checking memory…':'Process opportunity'}</button>
    <small>TheNag never applies automatically. It only prepares drafts, reminders, and checklists.</small>
  </div></div>
}
