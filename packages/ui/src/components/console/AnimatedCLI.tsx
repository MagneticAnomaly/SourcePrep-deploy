"use client";

import { useState, useEffect, useRef, useCallback } from 'react';
import type { CliScript, CliEvent } from './cli-types';
import { TerminalFrame } from './TerminalFrame';

export interface AnimatedCLIProps {
  /** Single script. Backwards-compatible. */
  script?: CliScript;
  /** Sequence of scripts. When provided, rotates through them on each completion. */
  scripts?: CliScript[];
  theme?: 'dark' | 'claude' | 'minimal';
  className?: string;
  contentClassName?: string;
  autoPlay?: boolean;
}

interface RenderedLine {
  id: number;
  content: string;
  className: string;
  prefix?: string;
}

/**
 * AnimatedCLI — the playback engine.
 *
 * Takes a CliScript (or a sequence via `scripts`) and steps through
 * each event, rendering lines into a terminal frame with typewriter
 * effects, thinking indicators, and tool-call styling. With a sequence,
 * it advances to the next script after each one completes.
 */
export function AnimatedCLI({
  script,
  scripts,
  theme = 'dark',
  className = '',
  contentClassName,
  autoPlay = true,
}: AnimatedCLIProps) {
  const allScripts = scripts && scripts.length > 0 ? scripts : script ? [script] : [];
  const [currentScriptIdx, setCurrentScriptIdx] = useState(0);
  const safeScriptIdx = Math.min(currentScriptIdx, Math.max(0, allScripts.length - 1));
  const currentScript = allScripts[safeScriptIdx];
  const [lines, setLines] = useState<RenderedLine[]>([]);
  const [currentEventIdx, setCurrentEventIdx] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const [typingText, setTypingText] = useState('');
  const [typingMeta, setTypingMeta] = useState<{ className: string; prefix?: string } | null>(null);
  const [showCursor, setShowCursor] = useState(true);
  const [isRunning] = useState(autoPlay);
  const lineIdRef = useRef(0);
  const processedIdxRef = useRef(-1);
  const scrollRef = useRef<HTMLDivElement>(null);

  const nextId = useCallback(() => ++lineIdRef.current, []);

  // Cursor blink
  useEffect(() => {
    const interval = setInterval(() => setShowCursor(p => !p), 530);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines, typingText]);

  // Add a completed line
  const addLine = useCallback((content: string, className: string, prefix?: string) => {
    setLines(prev => [...prev, { id: nextId(), content, className, prefix }]);
  }, [nextId]);

  // Main event processor
  useEffect(() => {
    if (!isRunning || isTyping || !currentScript) return;
    if (currentEventIdx >= currentScript.events.length) {
      // Script finished. Either advance to the next in a sequence,
      // loop the same script, or stop.
      const hasMoreScripts = allScripts.length > 1;
      const shouldContinue = hasMoreScripts || currentScript.loop !== false;
      if (shouldContinue) {
        const delay = currentScript.loopDelayMs ?? 3000;
        const timer = setTimeout(() => {
          setLines([]);
          if (hasMoreScripts) {
            setCurrentScriptIdx((p) => (p + 1) % allScripts.length);
          }
          setCurrentEventIdx(0);
          lineIdRef.current = 0;
          processedIdxRef.current = -1;
        }, delay);
        return () => clearTimeout(timer);
      }
      return;
    }

    if (processedIdxRef.current === currentEventIdx) return;
    processedIdxRef.current = currentEventIdx;

    const event = currentScript.events[currentEventIdx];
    processEvent(event);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentEventIdx, currentScriptIdx, isRunning, isTyping]);

  function processEvent(event: CliEvent) {
    switch (event.type) {
      case 'user_input':
        typeText(event.text, event.typingDelayMs ?? 35, 'text-[#e6edf3]', '❯ ');
        break;

      case 'agent_thinking': {
        const label = event.label ?? 'Thinking…';
        addLine(label, 'text-[#8b949e] italic animate-pulse');
        const timer = setTimeout(() => advance(), event.durationMs);
        return () => clearTimeout(timer);
      }

      case 'tool_call': {
        const argsDisplay = event.args ? `(${event.args})` : '()';
        addLine(`⚡ ${event.tool}${argsDisplay}`, 'text-[#79c0ff] font-semibold');
        if (event.statusText) {
          addLine(`  ${event.statusText}`, 'text-[#8b949e] text-xs italic');
        }
        const timer = setTimeout(() => advance(), event.durationMs);
        return () => clearTimeout(timer);
      }

      case 'tool_result': {
        const statusIcon = event.status === 'error' ? '✗' : event.status === 'info' ? 'ℹ' : '✓';
        const statusColor = event.status === 'error' ? 'text-[#f85149]' : event.status === 'info' ? 'text-[#79c0ff]' : 'text-[#3fb950]';
        // Support multi-line results
        const resultLines = event.text.split('\n');
        resultLines.forEach((line, i) => {
          const prefix = i === 0 ? `${statusIcon} ` : '  ';
          addLine(line, i === 0 ? statusColor : 'text-[#8b949e]', prefix);
        });
        advance();
        break;
      }

      case 'agent_output':
        if (event.typewriter !== false) {
          typeText(event.text, event.typewriterDelayMs ?? 15, 'text-[#c9d1d9]');
        } else {
          // Render all lines at once
          event.text.split('\n').forEach(line => {
            addLine(line, 'text-[#c9d1d9]');
          });
          advance();
        }
        break;

      case 'pause': {
        const timer = setTimeout(() => advance(), event.durationMs);
        return () => clearTimeout(timer);
      }

      case 'clear':
        setLines([]);
        advance();
        break;
    }
  }

  function typeText(fullText: string, delayMs: number, lineClass: string, prefix?: string) {
    setIsTyping(true);
    setTypingText('');
    setTypingMeta({ className: lineClass, prefix });

    let charIdx = 0;
    const interval = setInterval(() => {
      charIdx++;
      setTypingText(fullText.slice(0, charIdx));
      if (charIdx >= fullText.length) {
        clearInterval(interval);
        // Commit line to history
        addLine(fullText, lineClass, prefix);
        setIsTyping(false);
        setTypingText('');
        setTypingMeta(null);
        advance();
      }
    }, delayMs);
  }

  function advance() {
    setCurrentEventIdx(prev => prev + 1);
  }

  if (!currentScript) return null;

  return (
    <TerminalFrame title={currentScript.title ?? 'claude'} theme={theme} className={className} contentClassName={contentClassName}>
      <div ref={scrollRef} className="space-y-1">
        {/* Committed lines */}
        {lines.map(line => (
          <div key={line.id} className={`${line.className} whitespace-pre-wrap`}>
            {line.prefix && <span className="text-[#7ee787]">{line.prefix}</span>}
            {line.content}
          </div>
        ))}

        {/* Currently typing line */}
        {isTyping && typingMeta && (
          <div className={`${typingMeta.className} whitespace-pre-wrap`}>
            {typingMeta.prefix && <span className="text-[#7ee787]">{typingMeta.prefix}</span>}
            {typingText}
            <span className={`inline-block w-[2px] h-[1em] bg-[#58a6ff] ml-[1px] align-text-bottom ${showCursor ? 'opacity-100' : 'opacity-0'}`} />
          </div>
        )}

        {/* Idle cursor when not typing & script still running */}
        {!isTyping && currentEventIdx < currentScript.events.length && (
          <div className="text-[#e6edf3]">
            <span className="text-[#7ee787]">❯ </span>
            <span className={`inline-block w-[2px] h-[1em] bg-[#58a6ff] ml-[1px] align-text-bottom ${showCursor ? 'opacity-100' : 'opacity-0'}`} />
          </div>
        )}
      </div>
    </TerminalFrame>
  );
}
