import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Task = { id: string; repository: string; issue_number: number; status: string; current_agent: string | null; branch: string | null; pr_url: string | null; error: string | null; repair_attempts: number };
type Logs = { events: { status: string; agent: string | null; message: string; at: string }[]; tests: { exit_code: number; stdout: string; stderr: string; execution_time: number; timeout: boolean }[] };

const API = '/api';
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, { ...init, headers: { 'X-API-Key': sessionStorage.getItem('apiKey') || '', ...init?.headers } });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

function App() {
  const [repository, setRepository] = useState('');
  const [apiKey, setApiKey] = useState(sessionStorage.getItem('apiKey') || '');
  const [issue, setIssue] = useState('');
  const [id, setId] = useState(localStorage.getItem('taskId') || '');
  const [task, setTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<Logs | null>(null);
  const [diff, setDiff] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      try {
        const [nextTask, nextLogs, response] = await Promise.all([request<Task>(`/tasks/${id}`), request<Logs>(`/tasks/${id}/logs`), fetch(`${API}/tasks/${id}/diff`, { headers: { 'X-API-Key': sessionStorage.getItem('apiKey') || '' } })]);
        setTask(nextTask); setLogs(nextLogs); setDiff(await response.text()); setError('');
      } catch (e) { setError(String(e)); }
    };
    load(); const timer = setInterval(load, 3000); return () => clearInterval(timer);
  }, [id]);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError('');
    sessionStorage.setItem('apiKey', apiKey);
    try {
      const next = await request<Task>('/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repository, issue_number: Number(issue) }) });
      localStorage.setItem('taskId', next.id); setId(next.id); setTask(next);
    } catch (e) { setError(String(e)); }
  }
  async function cancel() { if (id) await request(`/tasks/${id}/cancel`, { method: 'POST' }); }
  const files = [...diff.matchAll(/^diff --git a\/(.*?) b\//gm)].map(match => match[1]);
  const latest = logs?.tests.at(-1);
  return <main>
    <header><h1>Issue Agent</h1><p>From GitHub issue to tested pull request</p></header>
    <form onSubmit={submit}><label>API key <input required type="password" value={apiKey} onChange={e => { setApiKey(e.target.value); sessionStorage.setItem('apiKey', e.target.value); }} /></label><label>Repository <input required placeholder="owner/repo" value={repository} onChange={e => setRepository(e.target.value)} /></label><label>Issue number <input required type="number" min="1" value={issue} onChange={e => setIssue(e.target.value)} /></label><button>Create task</button></form>
    {error && <p className="error">{error}</p>}
    {task && <>
      <section className="summary"><h2>Task {task.id}</h2><div className="grid"><span>Status <strong>{task.status}</strong></span><span>Current agent <strong>{task.current_agent || '—'}</strong></span><span>Repair attempts <strong>{task.repair_attempts} / 5</strong></span><span>Branch <strong>{task.branch || '—'}</strong></span></div>{task.pr_url && <p><a href={task.pr_url} target="_blank" rel="noreferrer">Open pull request ↗</a></p>}{task.error && <p className="error">{task.error}</p>}{!['completed', 'failed', 'cancelled'].includes(task.status) && <button className="secondary" onClick={cancel}>Cancel</button>}</section>
      <section><h2>Timeline</h2><ol>{logs?.events.map((event, i) => <li key={i}><time>{new Date(event.at).toLocaleString()}</time> <strong>{event.agent || event.status}</strong> — {event.message}</li>)}</ol></section>
      <section><h2>Changed files</h2>{files.length ? <ul>{files.map(file => <li key={file}>{file}</li>)}</ul> : <p>Available after review.</p>}</section>
      <section><h2>Tests</h2>{latest ? <><p>Exit {latest.exit_code} · {latest.execution_time.toFixed(1)}s {latest.timeout && '· timed out'}</p><pre>{(latest.stdout + '\n' + latest.stderr).trim()}</pre></> : <p>No test run yet.</p>}</section>
      <section><h2>Git diff</h2><pre>{diff || 'Available after review.'}</pre></section>
    </>}
  </main>;
}

createRoot(document.getElementById('root')!).render(<App />);
