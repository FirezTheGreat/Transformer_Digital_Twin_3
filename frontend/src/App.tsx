import React from 'react';
import { Activity } from 'lucide-react';

export default function App(): React.ReactElement {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6">
      <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl text-center">
        <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-emerald-500/10 text-emerald-400 mx-auto mb-4">
          <Activity className="w-6 h-6" />
        </div>
        <h1 className="text-xl font-semibold tracking-tight text-white mb-2">
          Transformer Digital Twin
        </h1>
        <p className="text-sm text-slate-400 mb-4">
          POWERNext-AI Hackathon 2026 — Track 2 (Team SKY HIGH)
        </p>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 text-xs text-slate-300 border border-slate-700">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          Environment Ready: Phase 0.1
        </div>
      </div>
    </div>
  );
}
