import { Check, X } from 'lucide-react'
import { Confirmation, needsDateConfirm } from './OpportunityCard.jsx'

const FIELDS = [['Location', 'location'], ['Work mode', 'work_mode'], ['Experience', 'experience'], ['Compensation', 'compensation'], ['Deadline', 'deadline'], ['Application link', 'application_link'], ['Source', 'source_creator']]

export default function DraftPanel({ item, onClose, onAction, onConfirmDate }) {
  const accepted = item.status === 'accepted'
  return <div className="drawer-backdrop" onClick={onClose}>
    <aside className="why-drawer" onClick={e => e.stopPropagation()}>
      <button className="close-button" onClick={onClose}><X size={20}/></button>
      <div className="eyebrow">Draft only</div>
      <h2>{item.title || 'Untitled opportunity'}</h2>
      <p className="drawer-subtitle">{item.company || 'Company not found'} · Accepting creates a calendar event and/or note. Nothing is ever submitted for you.</p>
      <section><div className="reason-list">{FIELDS.map(([label, key]) => <div key={key}><span><b>{label}:</b> {item[key] || 'Not provided'}</span></div>)}</div></section>
      <Confirmation items={item.confirmation}/>
      {needsDateConfirm(item) && <button className="process-button" onClick={() => onConfirmDate(item)}>Confirm date &amp; add to calendar</button>}
      <button className="process-button" disabled={accepted} onClick={() => onAction(item, 'accepted')}><Check size={18}/> {accepted ? 'Accepted' : 'Accept'}</button>
    </aside>
  </div>
}
