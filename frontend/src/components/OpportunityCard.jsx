import { Bookmark, BriefcaseBusiness, CalendarDays, Check, ChevronRight, CircleHelp, MapPin, Sparkles, Wifi } from 'lucide-react'

const confidenceTone = (score) => score >= 80 ? 'high' : score >= 55 ? 'medium' : 'low'

export const needsDateConfirm = item => item.status === 'accepted' && !item.calendar_event_id && item.deadline && item.deadline !== 'Not provided' && item.deadline_confidence !== 'green'

export const Confirmation = ({ items }) => items?.length ? <div className="confirmation">{items.map((c, i) => <div key={i}><Check size={14}/> {c.label}{c.url && <> · <a href={c.url} target="_blank" rel="noreferrer">Open</a></>}</div>)}</div> : null

export default function OpportunityCard({ item, onWhy, onAction, onDraft, onConfirmDate }) {
  const confidence = Math.round((item.extraction_confidence * .7) + (item.source_trust * .3))
  return (
    <article className={`opportunity-card ${item.rank >= 85 ? 'top-match' : ''}`}>
      <div className="card-topline">
        {item.personalized && <div className="rank-pill"><Sparkles size={13} /> {item.rank}% match</div>}
        <div className={`confidence ${confidenceTone(confidence)}`}><span /> {confidence}% confidence</div>
      </div>
      <div className="card-heading">
        <div className="company-mark">{item.company?.slice(0, 1) || 'T'}</div>
        <div><h3>{item.title || 'Untitled opportunity'}</h3><p>{item.company || 'Company not found'}</p></div>
      </div>
      <div className="meta-row">
        <span><MapPin size={14}/>{item.location}</span>
        <span><Wifi size={14}/>{item.work_mode}</span>
        <span><BriefcaseBusiness size={14}/>{item.employment_type}</span>
      </div>
      <div className="skills">{item.skills?.slice(0, 4).map(skill => <span key={skill}>{skill}</span>)}</div>
      {item.duplicate?.status !== 'new' && <button className={`change-notice ${item.duplicate.status}`} onClick={() => onWhy(item)}>
        <span className="pulse-dot"/><strong>{item.duplicate.label}</strong>
        {item.duplicate.changes?.[0] && <span>{item.duplicate.changes[0].before} → {item.duplicate.changes[0].after}</span>}
        <ChevronRight size={15}/>
      </button>}
      <div className="fact-grid">
        <div><span>Experience</span><strong>{item.experience}</strong></div>
        <div><span>Compensation</span><strong>{item.compensation}</strong></div>
        <div><span><CalendarDays size={12}/> Deadline</span><strong>{item.deadline}</strong></div>
      </div>
      <div className="source-line">
        <span>via {item.source_creator}</span><span className="dot">•</span>
        <span className={confidenceTone(item.source_trust)}>{item.source_trust}% source trust</span>
        <span className="observations">{item.source_detail?.observation_count ?? 0} observations</span>
      </div>
      <div className="card-actions">
        <button className="why-button" onClick={() => onWhy(item)}><CircleHelp size={16}/> Why this?</button>
        <button className={`save-button ${item.status === 'saved' ? 'saved' : ''}`} onClick={() => onAction(item, item.status === 'saved' ? 'skipped' : 'saved')}>
          <Bookmark size={16} fill={item.status === 'saved' ? 'currentColor' : 'none'}/>{item.status === 'saved' ? 'Saved' : 'Save'}
        </button>
        {item.status !== 'accepted' && item.status !== 'rejected' && <button className="save-button" onClick={() => onAction(item, 'rejected', window.prompt('Why not? (optional — e.g. fake, dead link, not relevant)') || undefined)}>Reject</button>}
        {item.status === 'accepted'
          ? <button className="review-button" onClick={() => onDraft(item)}>Accepted <Check size={16}/></button>
          : <><button className="save-button" onClick={() => onDraft(item)}>Review draft</button>
            <button className="review-button" onClick={() => onAction(item, 'accepted')}>Accept <ChevronRight size={16}/></button></>}
      </div>
      <Confirmation items={item.confirmation}/>
      {needsDateConfirm(item) && <button className="review-button" onClick={() => onConfirmDate(item)}>Confirm date &amp; add to calendar</button>}
    </article>
  )
}
