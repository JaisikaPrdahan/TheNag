import { FileVideo, LoaderCircle, Sparkles, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { apiFetch } from '../api.js'

export default function IntakeModal({ onClose, onProcessed }) {
  const [tab, setTab] = useState('link'); const [link, setLink] = useState(''); const [caption, setCaption] = useState(''); const [source, setSource] = useState(''); const [file, setFile] = useState(null); const [loading, setLoading] = useState(false); const [linkError, setLinkError] = useState(''); const input = useRef()
  const submit = async () => {
    setLoading(true); setLinkError('')
    try {
      let result
      if (tab === 'link') result = await apiFetch('/api/process-link', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:link, source_creator:source}) })
      else if (tab === 'upload' && file) { const body = new FormData(); body.append('file', file); body.append('caption', caption); body.append('source_creator', source); result = await apiFetch('/api/process-upload', { method:'POST', body }) }
      else result = await apiFetch('/api/process-caption', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({caption, source_creator:source}) })
      onProcessed(result)
    } catch (e) {
      if (tab === 'link' && e.detail?.error_type === 'AutoFetchFailed') {
        setTab('caption')
        setLinkError(e.detail.message || "Couldn't fetch that link automatically — paste the caption or upload the video instead.")
      } else setLinkError(e.message)
    }
    finally { setLoading(false) }
  }
  return <div className="modal-backdrop"><div className="intake-modal">
    <button className="close-button" onClick={onClose}><X size={20}/></button>
    <div className="eyebrow"><Sparkles size={15}/> Add an opportunity</div><h2>Turn a Reel into a useful decision</h2><p>Paste a reel link, its caption, or upload the video. TheNag extracts the details, checks memory, and prepares a draft-only next step.</p>
    <div className="input-tabs"><button className={tab==='link'?'active':''} onClick={()=>setTab('link')}>Paste link</button><button className={tab==='caption'?'active':''} onClick={()=>setTab('caption')}>Paste caption</button><button className={tab==='upload'?'active':''} onClick={()=>setTab('upload')}>Upload video</button></div>
    {tab === 'link' && <label>Reel or post link<input value={link} onChange={e=>setLink(e.target.value)} placeholder="https://www.instagram.com/reel/..."/></label>}
    {linkError && <div className="link-error">{linkError}</div>}
    {tab === 'upload' && <button className="dropzone" onClick={()=>input.current.click()}><input ref={input} hidden type="file" accept="video/*" onChange={e=>setFile(e.target.files[0])}/><FileVideo size={28}/><strong>{file?.name || 'Choose a Reel or video'}</strong><span>MP4, MOV or WebM · Whisper when enabled</span></button>}
    {tab !== 'link' && <label>Caption text<textarea value={caption} onChange={e=>setCaption(e.target.value)} placeholder="Example: React developer की भर्ती — remote role, 1–2 years experience, apply by 12 October…"/></label>}
    <label>Source creator <input value={source} onChange={e=>setSource(e.target.value)} placeholder="@creator (optional)"/></label>
    <div className="language-note">English · हिन्दी · Hinglish</div>
    <button className="process-button" disabled={loading || (tab==='link' ? !link.trim() : (!caption.trim() && !file))} onClick={submit}>{loading?<LoaderCircle className="spin" size={18}/>:<Upload size={18}/>} {loading?'Checking memory…':'Process opportunity'}</button>
    <small>TheNag never applies automatically. It only prepares drafts, reminders, and checklists.</small>
  </div></div>
}
