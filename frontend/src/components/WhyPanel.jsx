import { Brain, CheckCircle2, Database, History, ShieldCheck, X } from 'lucide-react'

export default function WhyPanel({ item, onClose }) {
  if (!item) return null
  const confidence = Math.round(item.extraction_confidence * .7 + item.source_trust * .3)
  return <div className="drawer-backdrop" onClick={onClose}>
    <aside className="why-drawer" onClick={e => e.stopPropagation()}>
      <button className="close-button" onClick={onClose}><X size={20}/></button>
      <div className="eyebrow"><Brain size={15}/> Memory-informed result</div>
      <h2>Why this opportunity?</h2>
      <p className="drawer-subtitle">A plain-language summary of what influenced this result—never hidden reasoning or raw prompts.</p>
      <div className="match-score"><strong>{item.rank}%</strong><div><b>Personal match</b><span>Based on your saved preferences and decisions</span></div></div>
      <section><h4>What matched your memory</h4>
        <div className="reason-list">{item.why?.map((reason, i) => <div key={i}><CheckCircle2 size={17}/><span>{reason}</span></div>)}</div>
      </section>
      <section><h4><History size={15}/> Seen before</h4>
        <p>{item.duplicate?.status === 'new' ? 'No close match was found in your history.' : item.duplicate?.label}</p>
        {item.duplicate?.changes?.map(change => <div className="field-change" key={change.field}><span>{change.field}</span><del>{change.before}</del><b>→</b><ins>{change.after}</ins></div>)}
      </section>
      <section><h4><ShieldCheck size={15}/> Confidence</h4>
        <div className="confidence-math"><div><strong>{item.extraction_confidence}%</strong><span>Extraction</span></div><b>+</b><div><strong>{item.source_trust}%</strong><span>Source history</span></div><b>=</b><div className="total"><strong>{confidence}%</strong><span>Combined</span></div></div>
        <p>{item.source_detail?.evidence || `This source has a ${item.source_trust}% trust score based on repeated observations.`}</p>
      </section>
      <section className="privacy-note"><Database size={18}/><div><b>Your memory stays private</b><p>Personal history is kept in your own memory bank. It is never included in verified B2B feeds.</p></div></section>
    </aside>
  </div>
}
