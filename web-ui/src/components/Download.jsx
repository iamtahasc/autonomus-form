import React from 'react';
import { Download as DownloadIcon, CheckCircle, RefreshCw, FileCheck } from 'lucide-react';
import { motion } from 'framer-motion';

export function Download({ url, filename, onReset }) {
    const handleDownload = () => {
        const downloadUrl = url.startsWith('http') ? url : `http://localhost:8000${url}`;
        window.open(downloadUrl, '_blank');
    };

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="text-center space-y-10 py-8"
        >
            <div className="flex flex-col items-center gap-6">
                <div className="relative">
                    <div className="absolute inset-0 bg-green-500/30 blur-2xl rounded-full" />
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-green-500/20 to-emerald-500/10 text-green-400 flex items-center justify-center border border-green-500/20 shadow-2xl relative z-10">
                        <CheckCircle className="w-12 h-12 drop-shadow-lg" />
                    </div>
                </div>

                <div className="space-y-2">
                    <h3 className="text-4xl font-bold text-white tracking-tight">Success!</h3>
                    <p className="text-slate-400 text-lg flex items-center justify-center gap-2">
                        <FileCheck className="w-5 h-5 text-slate-500" />
                        Converted <span className="text-slate-200 font-semibold">{filename}</span>
                    </p>
                </div>
            </div>

            <div className="flex flex-col gap-5 items-center w-full max-w-md mx-auto">
                <button
                    onClick={handleDownload}
                    className="w-full px-8 py-5 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-bold text-xl shadow-xl shadow-emerald-500/20 hover:shadow-emerald-500/30 transition-all duration-300 transform hover:-translate-y-1 flex items-center justify-center gap-3 group relative overflow-hidden"
                >
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent skew-x-12 translate-x-[-150%] group-hover:translate-x-[150%] transition-transform duration-700" />
                    <DownloadIcon className="w-7 h-7" />
                    <span>Download Fillable PDF</span>
                </button>

                <button
                    onClick={onReset}
                    className="px-6 py-3 text-slate-500 hover:text-slate-300 transition-all duration-200 text-sm font-medium flex items-center gap-2 hover:bg-white/5 rounded-xl border border-transparent hover:border-white/5"
                >
                    <RefreshCw className="w-4 h-4" />
                    Convert Another Document
                </button>
            </div>
        </motion.div>
    );
}
