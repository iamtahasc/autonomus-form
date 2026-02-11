import React, { useCallback, useState } from 'react';
import { Upload, FileType, ArrowUp } from 'lucide-react';
import { clsx } from 'clsx';

export function FileUpload({ onFileSelect, disabled }) {
    const [isDragging, setIsDragging] = useState(false);

    const handleDrag = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setIsDragging(true);
        } else if (e.type === 'dragleave') {
            setIsDragging(false);
        }
    }, []);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const file = e.dataTransfer.files[0];
            if (file.type === 'application/pdf') {
                onFileSelect(file);
            } else {
                alert("Please upload a PDF file.");
            }
        }
    }, [onFileSelect]);

    const handleChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            onFileSelect(e.target.files[0]);
        }
    };

    return (
        <div
            className={clsx(
                "relative group rounded-3xl border-2 border-dashed transition-all duration-300 cursor-pointer overflow-hidden p-12 md:p-20 outline-none focus:ring-4 focus:ring-purple-500/20",
                isDragging
                    ? "border-purple-500 bg-purple-500/10 scale-[1.02]"
                    : "border-slate-700 bg-slate-800/30 hover:border-purple-500/50 hover:bg-slate-800/50",
                disabled && "opacity-50 pointer-events-none"
            )}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => document.getElementById('file-upload').click()}
        >
            <input
                type="file"
                id="file-upload"
                className="hidden"
                accept=".pdf"
                onChange={handleChange}
                disabled={disabled}
            />

            {/* Glow effect on hover */}
            <div className="absolute inset-0 bg-gradient-to-tr from-purple-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            <div className="flex flex-col items-center gap-8 relative z-10">
                <div className={clsx(
                    "w-28 h-28 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl",
                    isDragging
                        ? "bg-purple-500 scale-110 shadow-purple-500/30"
                        : "bg-slate-800 group-hover:bg-slate-700 group-hover:scale-105 shadow-black/20"
                )}>
                    {isDragging ? (
                        <ArrowUp className="w-12 h-12 text-white animate-bounce" />
                    ) : (
                        <Upload className="w-12 h-12 text-purple-400 group-hover:text-purple-300" />
                    )}
                </div>

                <div className="text-center space-y-3">
                    <h3 className="text-3xl font-bold text-white group-hover:text-purple-100 transition-colors">
                        {isDragging ? "Drop to Upload" : "Upload Document"}
                    </h3>
                    <p className="text-slate-400 max-w-sm mx-auto text-base leading-relaxed">
                        Drag and drop your static PDF form here, <br /> or click to browse files from your computer.
                    </p>
                </div>

                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-800/80 border border-white/5 text-xs text-slate-400 font-medium tracking-wide uppercase">
                    <FileType className="w-3 h-3" />
                    <span>PDF up to 50MB</span>
                </div>
            </div>
        </div>
    );
}
