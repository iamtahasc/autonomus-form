import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { clsx } from 'clsx';
import { FileUpload } from './components/FileUpload';
import { ProgressBar } from './components/ProgressBar';
import { Download } from './components/Download';
import { Sparkles } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

function App() {
  const [file, setFile] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [downloadUrl, setDownloadUrl] = useState(null);

  const handleFileSelect = async (selectedFile) => {
    setFile(selectedFile);
    setStatus('uploading');
    setMessage('Uploading file...');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post(`${API_BASE}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setTaskId(response.data.task_id);
      setStatus('processing');
      setMessage('Queued for processing...');
    } catch (error) {
      console.error(error);
      setStatus('error');
      setMessage('Upload failed. Please check the server connection.');
    }
  };

  useEffect(() => {
    let interval;
    if (status === 'processing' && taskId) {
      interval = setInterval(async () => {
        try {
          const response = await axios.get(`${API_BASE}/status/${taskId}`);
          const data = response.data;

          setProgress(data.progress);
          setMessage(data.message);

          if (data.status === 'completed') {
            setStatus('completed');
            setDownloadUrl(data.download_url);
            clearInterval(interval);
          } else if (data.status === 'failed') {
            setStatus('error');
            setMessage(`Processing failed: ${data.message}`);
            clearInterval(interval);
          }
        } catch (error) {
          console.error("Polling error:", error);
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [status, taskId]);

  const handleReset = () => {
    setFile(null);
    setTaskId(null);
    setStatus('idle');
    setProgress(0);
    setMessage('');
    setDownloadUrl(null);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white selection:bg-purple-500/30 overflow-hidden relative font-sans">
      {/* Background Gradients */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-600/20 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-600/20 rounded-full blur-[120px] animate-pulse delay-1000" />
      </div>

      <div className="relative z-10 container mx-auto px-6 py-12 md:py-20 flex flex-col items-center justify-center min-h-screen">

        {/* Header Section */}
        <header className="text-center mb-16 space-y-6 max-w-4xl animate-fade-in-up">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-md mb-4 hover:bg-white/10 transition-colors cursor-default select-none">
            <Sparkles className="w-4 h-4 text-amber-300" />
            <span className="text-sm font-medium text-slate-300">AI-Powered PDF Converter</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight leading-tight drop-shadow-lg">
            Transform Your <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 animate-gradient bg-300%">
              Static Forms
            </span>
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Instantly convert non-fillable PDFs into smart, interactive fillable forms.
            No manual editing required.
          </p>
        </header>

        {/* Main Content Card */}
        <main className="w-full max-w-3xl">
          <div className="glass-panel p-1 rounded-3xl shadow-2xl shadow-purple-900/20 ring-1 ring-white/10 bg-gradient-to-b from-white/10 to-transparent backdrop-blur-xl">
            <div className="bg-slate-900/80 rounded-[22px] p-8 md:p-14 min-h-[500px] flex items-center justify-center relative overflow-hidden backdrop-blur-sm transition-all duration-500 border border-white/5">

              {/* Inner ambient glow */}
              <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/5 via-transparent to-purple-500/5 pointer-events-none" />

              <div className="w-full relative z-10">
                {status === 'idle' && (
                  <FileUpload onFileSelect={handleFileSelect} />
                )}

                {(status === 'uploading' || status === 'processing') && (
                  <ProgressBar
                    progress={progress}
                    message={message}
                    status={status}
                  />
                )}

                {status === 'completed' && (
                  <Download
                    url={downloadUrl}
                    filename={file?.name}
                    onReset={handleReset}
                  />
                )}

                {status === 'error' && (
                  <div className="text-center space-y-6">
                    <div className="w-20 h-20 mx-auto bg-red-500/10 rounded-full flex items-center justify-center border border-red-500/20 shadow-lg shadow-red-500/10">
                      <span className="text-3xl">⚠️</span>
                    </div>
                    <div>
                      <h3 className="text-2xl font-bold text-red-400 mb-3">Process Failed</h3>
                      <p className="text-slate-400 max-w-md mx-auto">{message}</p>
                    </div>
                    <button
                      onClick={handleReset}
                      className="px-8 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all duration-200 text-sm font-semibold border border-white/10 hover:border-white/20"
                    >
                      Try Again
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>

        <footer className="mt-20 text-center text-slate-600 text-sm">
          <p>© {new Date().getFullYear()}</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
