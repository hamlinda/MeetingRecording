import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

function App() {
  const [isRecording, setIsRecording] = useState(false)
  const [recordings, setRecordings] = useState([])
  const [config, setConfig] = useState({ ollama_url: '', ollama_model: '', summary_prompt: '', system_speaker_name: '' })
  const [selectedId, setSelectedId] = useState(null)
  const [isConfigOpen, setIsConfigOpen] = useState(false)
  const [availableModels, setAvailableModels] = useState([])
  const [isFetchingModels, setIsFetchingModels] = useState(false)
  const [fetchError, setFetchError] = useState(null)
  const [captureMic, setCaptureMic] = useState(true)
  const [captureVideo, setCaptureVideo] = useState(false)
  const [aiStatus, setAiStatus] = useState('checking')
  const [liveTranscript, setLiveTranscript] = useState("")
  const [audioAvailable, setAudioAvailable] = useState(true)
  const pollInterval = useRef(null)
  const mediaRecorderRef = useRef(null)
  const videoChunksRef = useRef([])
  const transcriptWindowRef = useRef(null)

  useEffect(() => {
    fetchConfig()
    fetchStatus()
    fetchRecordings()
    
    pollInterval.current = setInterval(() => {
      fetchStatus()
      fetchRecordings()
      fetchAiStatus()
    }, 3000)
    
    return () => clearInterval(pollInterval.current)
  }, [])

  useEffect(() => {
    if (isRecording && transcriptWindowRef.current && !transcriptWindowRef.current.closed) {
      const activeRec = recordings.find(r => r.status === 'recording')
      if (activeRec && activeRec.transcription) {
          setLiveTranscript(activeRec.transcription)
          transcriptWindowRef.current.document.getElementById('transcript-content').innerText = activeRec.transcription
          transcriptWindowRef.current.scrollTo(0, transcriptWindowRef.current.document.body.scrollHeight)
      }
    }
  }, [isRecording, recordings])

  const openTranscriptionWindow = () => {
    const win = window.open('', 'TranscriptionWindow', 'width=600,height=800,menubar=no,toolbar=no,location=no,status=no')
    win.document.write(`
      <html>
        <head>
          <title>Live Transcription</title>
          <style>
            body { font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; line-height: 1.6; }
            h2 { color: #6366f1; border-bottom: 1px solid #1e293b; padding-bottom: 0.5rem; margin-bottom: 1.5rem; }
            #transcript-content { white-space: pre-wrap; font-size: 1.1rem; }
          </style>
        </head>
        <body>
          <h2>Real-time Transcription</h2>
          <div id="transcript-content">Waiting for audio...</div>
        </body>
      </html>
    `)
    transcriptWindowRef.current = win
  }

  // Auto-select latest recording if none selected
  useEffect(() => {
    if (!selectedId && recordings.length > 0) {
      setSelectedId(recordings[0].id)
    }
  }, [recordings, selectedId])

  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config')
      const data = await res.json()
      setConfig(data)
    } catch (e) { console.error("Could not fetch config", e) }
  }

  const fetchModels = async (url) => {
    setIsFetchingModels(true)
    setFetchError(null)
    try {
      const res = await fetch(`/api/ollama/models?url=${encodeURIComponent(url)}`)
      const data = await res.json()
      if (data.status === 'success') {
        setAvailableModels(data.models || [])
        if (!config.ollama_model && data.models && data.models.length > 0) {
           setConfig(prev => ({...prev, ollama_model: data.models[0]}))
        }
      } else {
        setAvailableModels([])
        setFetchError(data.detail || "Server returned an error")
      }
    } catch (e) {
      console.error("Could not fetch models", e)
      setAvailableModels([])
      setFetchError(e.message)
    } finally {
      setIsFetchingModels(false)
    }
  }

  const saveConfig = async (e) => {
    e.preventDefault()
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })
      setIsConfigOpen(false)
    } catch (e) { alert("Failed to save config") }
  }

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/recording/status')
      const data = await res.json()
      setIsRecording(data.is_recording)
      setAudioAvailable(data.audio_recording_available !== false)
    } catch (e) { console.error("Could not fetch status", e) }
  }

  const fetchRecordings = async () => {
    try {
      const res = await fetch('/api/recordings')
      const data = await res.json()
      data.sort((a,b) => new Date(b.start_time || 0) - new Date(a.start_time || 0))
      setRecordings(data)
    } catch (e) { console.error("Could not fetch recordings", e) }
  }

  const fetchAiStatus = async () => {
    try {
      const res = await fetch('/api/ai-check')
      const data = await res.json()
      setAiStatus(data.status)
    } catch (e) { setAiStatus('offline') }
  }

  const deleteRecording = async (id) => {
    if (!window.confirm("Are you sure? This deletes audio and transcript.")) return;
    try {
      await fetch(`/api/recording/${id}`, { method: 'DELETE' });
      setSelectedId(null)
      fetchRecordings();
    } catch (e) { alert("Failed to delete."); }
  }

  const renameRecording = async (id, newTitle) => {
    try {
      await fetch(`/api/recording/${id}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle })
      });
      fetchRecordings();
    } catch (e) { alert("Failed to rename."); }
  }

  const suggestTitle = async (id) => {
    try {
      const res = await fetch(`/api/recording/${id}/suggest-title`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      fetchRecordings();
    } catch (e) { alert("Failed to suggest title: " + e.message); }
  }

  const reprocessRecording = async (id) => {
    try {
      const res = await fetch(`/api/recording/${id}/reprocess`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      fetchRecordings();
    } catch (e) { alert("Failed to re-process: " + e.message); }
  }

  const toggleRecording = async () => {
    try {
      if (isRecording) {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
          mediaRecorderRef.current.stop();
        } else {
          const res = await fetch('/api/recording/stop', { method: 'POST' })
          if (!res.ok) throw new Error(await res.text());
          setIsRecording(false)
          fetchRecordings()
        }
      } else {
        let stream = null;
        if (captureVideo) {
          try {
             stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
          } catch (e) {
             console.warn("User cancelled video capture.", e);
             return;
          }
        }
        
        const res = await fetch('/api/recording/start', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ record_mic: captureMic })
        })
        if (!res.ok) {
           if (stream) stream.getTracks().forEach(t => t.stop());
           throw new Error(await res.text());
        }
        
        if (stream) {
          videoChunksRef.current = [];
          const mr = new MediaRecorder(stream, { mimeType: 'video/webm' });
          mr.ondataavailable = e => {
            if (e.data && e.data.size > 0) videoChunksRef.current.push(e.data);
          };
          mr.onstop = async () => {
            stream.getTracks().forEach(t => t.stop());
            const blob = new Blob(videoChunksRef.current, { type: 'video/webm' });
            const formData = new FormData();
            formData.append('video_data', blob, 'video.webm');
            
            try {
              await fetch('/api/recording/stop', { method: 'POST', body: formData });
              setIsRecording(false);
              fetchRecordings();
            } catch (e) {
              alert("Error saving video recording: " + e.message);
              setIsRecording(false);
              fetchRecordings();
            }
          };
          mediaRecorderRef.current = mr;
          mr.start();
        }
        
        setIsRecording(true)
        fetchRecordings()
      }
    } catch (e) { alert("Error: " + e.message) }
  }

  const isServicesMissing = !audioAvailable || aiStatus !== 'online'
  const selectedRecording = recordings.find(r => r.id === selectedId)

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="sidebar-header">
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
             <div>
                <h2 style={{ fontSize: '1.2rem', margin: 0, backgroundImage: 'linear-gradient(135deg, var(--primary-color), var(--secondary-color))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  Recorder
                </h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: aiStatus === 'online' ? 'var(--success-color)' : aiStatus === 'offline' ? 'var(--danger-color)' : 'var(--warning-color)' }}></div>
                    <span style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: 'var(--text-secondary)', fontWeight: 700 }}>AI {aiStatus}</span>
                </div>
             </div>
             <button 
               className="btn" 
               style={{ padding: '0.4rem', borderRadius: '4px', opacity: isServicesMissing ? 0.5 : 1, cursor: isServicesMissing ? 'not-allowed' : 'pointer' }} 
               onClick={() => !isServicesMissing && setIsConfigOpen(!isConfigOpen)}
               disabled={isServicesMissing}
               title={isServicesMissing ? "System services are offline" : "Configure AI settings"}
             >
               ⚙️
             </button>
            </div>
        </header>

        <section className="sidebar-controls">
          {isServicesMissing && (
            <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: '8px', padding: '12px', margin: '0 12px 12px 12px', fontSize: '0.8rem', lineHeight: '1.4', color: '#fca5a5' }}>
               <p style={{ margin: 0, fontWeight: 'bold', marginBottom: '4px' }}>⚠️ System Requirements Missing</p>
               <p style={{ margin: 0 }}>
                 Audio recording components or Ollama AI services are not fully running on this host server.
                 Recording and configuration have been disabled.
               </p>
               <p style={{ margin: '8px 0 0 0', fontWeight: 600 }}>
                 Please download the Windows Standalone (below) or clone the repository from <a href="https://github.com/hamlinda/Meetingrecording.git" target="_blank" rel="noopener noreferrer" style={{ color: '#a5b4fc', textDecoration: 'underline' }}>github.com/hamlinda/Meetingrecording.git</a> to run locally.
               </p>
               <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(0,0,0,0.25)', borderRadius: '6px', fontSize: '0.72rem', color: '#e2e8f0', textAlign: 'left' }}>
                 <strong style={{ display: 'block', marginBottom: '2px' }}>Windows Standalone Setup:</strong>
                 <ol style={{ margin: 0, paddingLeft: '14px' }}>
                   <li>Extract the downloaded ZIP archive.</li>
                   <li>Double-click <code>setup.bat</code> to initialize dependencies and compile assets.</li>
                   <li>Double-click <code>Launch.vbs</code> to run the application natively.</li>
                 </ol>
               </div>
            </div>
          )}
          <div className="recorder-container">
            <div className="record-btn-wrapper">
              {isRecording && <div className="record-btn-pulse"></div>}
              <button 
                className={`record-btn ${isRecording ? 'recording' : ''}`}
                onClick={toggleRecording}
                disabled={isServicesMissing && !isRecording}
                style={{ opacity: (isServicesMissing && !isRecording) ? 0.4 : 1, cursor: (isServicesMissing && !isRecording) ? 'not-allowed' : 'pointer' }}
                title={isServicesMissing ? "Recording is disabled due to missing local services" : "Start recording"}
              >
                {isRecording ? 'STOP' : 'REC'}
              </button>
            </div>
            <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255,255,255,0.05)', padding: '8px 12px', borderRadius: '8px' }}>
                    <label htmlFor="micToggle" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                      Microphone
                    </label>
                    <label className="switch">
                        <input 
                          type="checkbox" 
                          id="micToggle" 
                          checked={captureMic} 
                          disabled={isRecording || isServicesMissing}
                          onChange={e => setCaptureMic(e.target.checked)} 
                        />
                        <span className="slider"></span>
                    </label>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255,255,255,0.05)', padding: '8px 12px', borderRadius: '8px' }}>
                    <label htmlFor="videoToggle" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                      Screen Capture
                    </label>
                    <label className="switch">
                        <input 
                          type="checkbox" 
                          id="videoToggle" 
                          checked={captureVideo} 
                          disabled={isRecording || isServicesMissing}
                          onChange={e => setCaptureVideo(e.target.checked)} 
                        />
                        <span className="slider"></span>
                    </label>
                </div>
            </div>
            
            <div style={{ marginTop: '1.25rem', width: '100%' }}>
                <button 
                  className="btn btn-secondary" 
                  style={{ width: '100%', gap: '8px', opacity: isServicesMissing ? 0.5 : 1, cursor: isServicesMissing ? 'not-allowed' : 'pointer' }}
                  onClick={() => !isServicesMissing && openTranscriptionWindow()}
                  disabled={isServicesMissing}
                >
                  📺 Live View Window
                </button>
            </div>

            <div style={{ marginTop: '1rem', width: '100%', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1rem' }}>
                <a 
                  href="/api/download/windows-standalone"
                  className="btn"
                  style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', background: 'rgba(255,255,255,0.1)', color: '#fff', textDecoration: 'none', fontSize: '0.85rem' }}
                >
                  📦 Windows Standalone
                </a>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '8px', textAlign: 'center', lineHeight: '1.4' }}>
                  ⚠️ <strong>Notice:</strong> If you are not running the backend on the local Windows system accessing it, this standalone mode will not work.
                </p>
            </div>
          </div>
        </section>

        <div className="sidebar-recordings">
           <h3>Meetings</h3>
           {recordings.map(rec => (
             <div 
               key={rec.id} 
               className={`recording-nav-item ${selectedId === rec.id ? 'active' : ''}`}
               onClick={() => setSelectedId(rec.id)}
             >
               <div className="recording-nav-title">{rec.title || "Untitled"}</div>
               <div className="recording-nav-meta">
                 <span>{rec.start_time ? new Date(rec.start_time).toLocaleDateString() : 'N/A'}</span>
                 <span className={`status-badge status-${rec.status.split(':')[0]}`}>{rec.status.split(' ')[0]}</span>
               </div>
             </div>
           ))}
        </div>
      </aside>

      <main className="main-content">
        {isConfigOpen && (
          <form className="glass-panel config-panel" style={{ position: 'absolute', top: '1rem', right: '1rem', zIndex: 100, width: '400px' }} onSubmit={saveConfig}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <h3>AI Configuration</h3>
                <button type="button" onClick={() => setIsConfigOpen(false)}>×</button>
            </div>
            <div className="input-group">
              <label>Ollama Server URL</label>
              <input className="input-control" type="url" required value={config.ollama_url} onChange={e => setConfig({...config, ollama_url: e.target.value})} />
              <button type="button" className="btn btn-primary" onClick={() => fetchModels(config.ollama_url)} disabled={isFetchingModels}>
                {isFetchingModels ? "..." : "Fetch Models"}
              </button>
            </div>
            <div className="input-group">
              <label>Ollama Model</label>
              <select className="input-control" value={config.ollama_model} onChange={e => setConfig({...config, ollama_model: e.target.value})}>
                {availableModels.map(model => <option key={model} value={model}>{model}</option>)}
              </select>
            </div>
            <div className="input-group">
              <label>System Speaker Name</label>
              <input className="input-control" type="text" value={config.system_speaker_name || ""} onChange={e => setConfig({...config, system_speaker_name: e.target.value})} />
            </div>
            <button type="submit" className="btn btn-primary">Save</button>
          </form>
        )}

        {selectedRecording ? (
          <div className="fade-in">
            <header className="detail-header">
              <div>
                <h1 
                  style={{ textAlign: 'left', margin: 0, cursor: 'pointer', fontSize: '2rem' }}
                  onClick={() => {
                    const t = prompt("New title:", selectedRecording.title);
                    if (t) renameRecording(selectedRecording.id, t);
                  }}
                >
                  {selectedRecording.title || "Untitled Meeting"}
                </h1>
                <div style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                  {new Date(selectedRecording.start_time).toLocaleString()} • {selectedRecording.id.substring(0,8)}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                {selectedRecording.status === 'completed' && selectedRecording.media_path && (
                  <button 
                    className="btn btn-primary" 
                    onClick={() => {
                      const url = `/recordings/${selectedRecording.id}/${selectedRecording.media_path.split(/[\\/]/).pop()}`
                      window.open(url, '_blank')
                    }}
                  >
                    ▶️ Play Combined
                  </button>
                )}
                {selectedRecording.status !== 'recording' && (
                    <button className="btn" onClick={() => reprocessRecording(selectedRecording.id)}>🔄 Reprocess</button>
                )}
                <button className="btn" onClick={() => suggestTitle(selectedRecording.id)}>✨ Auto-Title</button>
                <button className="btn" style={{ background: 'var(--danger-color)' }} onClick={() => deleteRecording(selectedRecording.id)}>🗑️ Delete</button>
              </div>
            </header>

            <div className="glass-panel" style={{ marginBottom: '2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                 <div className={`status-badge status-${selectedRecording.status.split(':')[0]}`}>
                    {selectedRecording.status}
                 </div>
                 {selectedRecording.media_path && (
                    selectedRecording.media_path.toLowerCase().endsWith('.webm') ? (
                      <video controls className="video-player-mini" style={{ height: '32px', maxWidth: '300px', borderRadius: '4px', backgroundColor: '#000' }}>
                          <source src={`/recordings/${selectedRecording.id}/${selectedRecording.media_path.split(/[\\/]/).pop()}`} type="video/webm" />
                      </video>
                    ) : (
                      <audio controls className="audio-player-mini" style={{ height: '32px' }}>
                          <source src={`/recordings/${selectedRecording.id}/${selectedRecording.media_path.split(/[\\/]/).pop()}`} type="audio/mpeg" />
                      </audio>
                    )
                 )}
              </div>
              
              {selectedRecording.media_path && selectedRecording.media_path.toLowerCase().endsWith('.webm') && (
                  <div style={{ marginBottom: '1rem', width: '100%', display: 'flex', justifyContent: 'center', backgroundColor: '#000', borderRadius: '8px', overflow: 'hidden' }}>
                      <video controls style={{ width: '100%', maxHeight: '400px' }}>
                          <source src={`/recordings/${selectedRecording.id}/${selectedRecording.media_path.split(/[\\/]/).pop()}`} type="video/webm" />
                      </video>
                  </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                <section>
                  <details>
                    <summary className="section-summary">Transcription</summary>
                    <div className="history-text">
                      {selectedRecording.transcription ? <ReactMarkdown>{selectedRecording.transcription}</ReactMarkdown> : "Processing..."}
                    </div>
                  </details>
                </section>
                <section>
                  <details>
                    <summary className="section-summary">AI Summary</summary>
                    <div className="history-text" style={{ borderLeft: '2px solid var(--primary-color)' }}>
                      {selectedRecording.summary ? <ReactMarkdown>{selectedRecording.summary}</ReactMarkdown> : "Waiting for summary..."}
                    </div>
                  </details>
                </section>
              </div>

              {selectedRecording.error_detail && (
                <div className="error-box fade-in">
                    <h5>⚠️ Error Identified</h5>
                    <div className="error-details">
                        {selectedRecording.error_detail}
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '1rem' }}>
                        You can try fixing your AI configuration or ensuring Ollama is running, then click <strong>Reprocess</strong> above.
                    </p>
                </div>
              )}
            </div>

            {selectedRecording.status === 'completed' && (
               <details className="glass-panel" style={{ padding: '1rem' }}>
                 <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>📊 Telemetry</summary>
                 <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1rem', fontSize: '0.85rem' }}>
                    <div><strong>Type:</strong> {selectedRecording.record_type}</div>
                    <div><strong>Model (T):</strong> {selectedRecording.transcription_model}</div>
                    <div><strong>Model (S):</strong> {selectedRecording.summarization_model}</div>
                    <div><strong>Time:</strong> {((new Date(selectedRecording.end_time) - new Date(selectedRecording.start_time)) / 1000).toFixed(1)}s</div>
                 </div>
               </details>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <h2>No Meeting Selected</h2>
            <p>Select a meeting from the sidebar to view details or start a new recording.</p>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
