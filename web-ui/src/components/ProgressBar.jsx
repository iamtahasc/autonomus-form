import React from 'react';
import { motion } from 'framer-motion';
import { Loader2, Sparkles } from 'lucide-react';

export function ProgressBar({ progress, message, status }) {
    return (
        <div className="w-full max-w-lg mx-auto space-y-8 py-10">

            <div className="space-y-2">
                <div className="flex justify-between items-end">
                    <span className="text-slate-300 font-medium tracking-wide flex items-center gap-2">
                        {status === 'processing' && <Sparkles className="w-4 h-4 text-purple-400 animate-pulse" />}
                        {message}
                    </span>
                    <span className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
                        {progress}%
                    </span>
                </div>

                <div className="h-8 bg-slate-900/50 rounded-full overflow-hidden backdrop-blur-sm border border-white/10 relative shadow-inner p-1">
                    <motion.div
                        className="h-full rounded-full bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 relative overflow-hidden"
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.5, ease: "easeInOut" }}
                    >
                        {/* Shimmer effect */}
                        <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/40 to-transparent skew-x-12 animate-[shimmer_1.5s_infinite]" />

                        {/* Glow at the tip */}
                        <div className="absolute right-0 top-0 bottom-0 w-2 bg-white/50 blur-[2px]" />
                    </motion.div>
                </div>
            </div>

            {status === 'processing' && (
                <div className="flex flex-col items-center justify-center gap-3 text-slate-500 text-sm animate-pulse pt-4">
                    <div className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-purple-500" />
                        <span>AI is analyzing document structure...</span>
                    </div>
                </div>
            )}
        </div>
    );
}
