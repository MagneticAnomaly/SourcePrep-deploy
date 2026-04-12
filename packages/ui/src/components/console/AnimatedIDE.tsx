"use client";

import { useState, useEffect, useRef, useCallback } from 'react';
import type { CliScript, CliEvent } from './cli-types';

export interface AnimatedIDEProps {
  script: CliScript;
  className?: string;
  autoPlay?: boolean;
}

interface ChatMessage {
  id: number;
  type: 'user' | 'agent' | 'tool';
  content: string;
  toolName?: string;
  toolStatus?: 'running' | 'success' | 'error' | 'info';
}

/**
 * AnimatedIDE
 * 
 * Mimics an IDE (like Windsurf or Cursor) with a split-pane layout:
 * - Left Pane: Code Editor view (updates on 'file_open' and 'code_edit')
 * - Right Pane: Agent Chat Sidebar (updates on other events)
 */
export function AnimatedIDE({
  script,
  className = '',
  autoPlay = true,
}: AnimatedIDEProps) {
  // Global script state
  const [currentEventIdx, setCurrentEventIdx] = useState(0);
  const [isRunning] = useState(autoPlay);
  const [isTyping, setIsTyping] = useState(false);

  // Editor State
  const [activeFile, setActiveFile] = useState<string>('Welcome');
  const [fileContent, setFileContent] = useState<string>('// Ask the agent to open or edit a file.');
  
  // Chat State
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [activeTypingText, setActiveTypingText] = useState('');
  const [activeToolInfo, setActiveToolInfo] = useState<{name: string, content: string} | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const msgIdRef = useRef(0);
  const nextId = useCallback(() => ++msgIdRef.current, []);

  // Auto-scroll chat
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatHistory, activeTypingText, activeToolInfo]);

  // Main Event Loop
  useEffect(() => {
    if (!isRunning || isTyping) return;
    if (currentEventIdx >= script.events.length) {
      if (script.loop !== false) {
        const timer = setTimeout(() => {
          setChatHistory([]);
          setActiveFile('Welcome');
          setFileContent('// Ask the agent to open or edit a file.');
          setCurrentEventIdx(0);
          msgIdRef.current = 0;
        }, script.loopDelayMs ?? 4000);
        return () => clearTimeout(timer);
      }
      return;
    }

    const event = script.events[currentEventIdx];
    processEvent(event);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentEventIdx, isRunning, isTyping]);

  function advance() {
    setCurrentEventIdx(prev => prev + 1);
  }

  function addMessage(msg: Omit<ChatMessage, 'id'>) {
    setChatHistory(prev => [...prev, { ...msg, id: nextId() }]);
  }

  function processEvent(event: CliEvent) {
    switch (event.type) {
      case 'user_input':
        // Show user typing it into the input box first, then commit
        typeUserCommand(event.text, event.typingDelayMs ?? 25);
        break;

      case 'agent_thinking': {
        addMessage({ type: 'agent', content: '...' });
        const timer = setTimeout(() => {
          // Remove the thinking placeholder
          setChatHistory(prev => prev.filter(m => m.content !== '...'));
          advance();
        }, event.durationMs);
        return () => clearTimeout(timer);
      }

      case 'tool_call': {
        setActiveToolInfo({ name: event.tool, content: event.args });
        const timer = setTimeout(() => advance(), event.durationMs);
        return () => clearTimeout(timer);
      }

      case 'tool_result': {
        if (activeToolInfo) {
          addMessage({
            type: 'tool',
            toolName: activeToolInfo.name,
            content: `Show Details v\n${event.text}`,
            toolStatus: event.status ?? 'success'
          });
          setActiveToolInfo(null);
        }
        advance();
        break;
      }

      case 'agent_output':
        typeAgentText(event.text, event.typewriterDelayMs ?? 10);
        break;

      case 'file_open':
        setActiveFile(event.filePath);
        setFileContent(event.content);
        if (event.durationMs) {
          const timer = setTimeout(() => advance(), event.durationMs);
          return () => clearTimeout(timer);
        } else {
          advance();
        }
        break;

      case 'code_edit': {
        setActiveFile(event.filePath);
        if (event.newContent) {
            setFileContent(event.newContent);
        } else if (event.diffText) {
            setFileContent(event.diffText);
        }
        const editTimer = setTimeout(() => advance(), event.durationMs);
        return () => clearTimeout(editTimer);
      }

      case 'pause': {
        const timer = setTimeout(() => advance(), event.durationMs);
        return () => clearTimeout(timer);
      }

      case 'clear':
        setChatHistory([]);
        advance();
        break;
    }
  }

  // Typewriter effects
  function typeUserCommand(fullText: string, delayMs: number) {
    setIsTyping(true);
    let charIdx = 0;
    const interval = setInterval(() => {
      charIdx++;
      setActiveTypingText(fullText.slice(0, charIdx));
      if (charIdx === fullText.length) {
        clearInterval(interval);
        // Wait a beat before "submitting"
        setTimeout(() => {
            addMessage({ type: 'user', content: fullText });
            setActiveTypingText('');
            setIsTyping(false);
            advance();
        }, 400);
      }
    }, delayMs);
  }

  function typeAgentText(fullText: string, delayMs: number) {
    setIsTyping(true);
    let charIdx = 0;
    const interval = setInterval(() => {
      charIdx++;
      setActiveTypingText(fullText.slice(0, charIdx));
      if (charIdx === fullText.length) {
        clearInterval(interval);
        addMessage({ type: 'agent', content: fullText });
        setActiveTypingText('');
        setIsTyping(false);
        advance();
      }
    }, delayMs);
  }

  return (
    <div className={`flex w-full h-[500px] rounded-xl overflow-hidden border border-[#303030] bg-[#1e1e1e] font-sans text-[13px] shadow-2xl shadow-black/40 ${className}`}>
      
      {/* LEFT: Code Editor Pane */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[#303030]">
        
        {/* Editor Tabs */}
        <div className="flex h-9 bg-[#181818] border-b border-[#303030]">
           <div className="flex items-center px-4 bg-[#1e1e1e] text-[#cccccc] border-t-2 border-t-[#007acc] border-r border-r-[#303030] cursor-default shrink-0 max-w-full">
              <span className="truncate">{activeFile}</span>
              <span className="ml-2 text-[#cccccc] hover:text-white cursor-pointer select-none">×</span>
           </div>
        </div>

        {/* Editor Content Area */}
        <div className="flex-1 overflow-auto bg-[#1e1e1e]">
            {/* Minimal line numbers + content simulating Monaco editor */}
            <div className="flex font-mono text-[13px] leading-6 py-4">
                <div className="w-12 text-right text-[#858585] select-none pr-4 shrink-0">
                    {fileContent.split('\n').map((_, i) => (
                        <div key={i}>{i + 1}</div>
                    ))}
                </div>
                <div className="text-[#d4d4d4] whitespace-pre flex-1 overflow-x-auto">
                    {fileContent}
                </div>
            </div>
        </div>

        {/* Status Bar */}
        <div className="h-[22px] bg-[#007acc] text-white flex items-center px-2 text-[11px]">
            <span className="mr-4">CoDRAG Project</span>
            <span className="mr-4">main*</span>
            <span className="flex-1"></span>
            <span>TypeScript</span>
        </div>
      </div>

      {/* RIGHT: Agent Sidebar */}
      <div className="w-[360px] flex flex-col bg-[#252526] shrink-0 border-l border-[#000000]">
        
        {/* Sidebar Header */}
        <div className="h-9 flex items-center px-4 font-medium text-[#cccccc] uppercase tracking-wider text-[11px] shadow-sm z-10 border-b border-[#303030]">
            AGENT
        </div>

        {/* Chat Scroll Area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-5 scroll-smooth">
            {chatHistory.map(msg => (
                <div key={msg.id} className="flex flex-col">
                    {msg.type === 'user' && (
                        <div className="bg-[#303031] text-[#e3e3e3] p-3 rounded-lg self-end max-w-[90%] break-words">
                            {msg.content}
                        </div>
                    )}
                    {msg.type === 'agent' && msg.content === '...' && (
                        <div className="text-[#8b8b8b] self-start w-full leading-relaxed italic animate-pulse text-xs">
                            Thinking…
                        </div>
                    )}
                    {msg.type === 'agent' && msg.content !== '...' && (
                        <div className="text-[#cccccc] self-start w-full leading-relaxed whitespace-pre-wrap">
                            {msg.content}
                        </div>
                    )}
                    {msg.type === 'tool' && (
                        <div className="bg-[#1e1e1e] border border-[#303030] rounded p-2 text-[#cccccc] mt-1 text-xs">
                           <div className="flex items-center gap-2 mb-1 opacity-80 font-medium">
                              <span className="text-[#007acc]">⚡</span> MCP Tool: {msg.toolName}
                           </div>
                           <div className="pl-5 opacity-60 m-0">
                              {msg.content}
                           </div>
                        </div>
                    )}
                </div>
            ))}

            {/* In-Flight Typist for Agent */}
            {!isTyping && activeToolInfo && (
                <div className="bg-[#1e1e1e] border border-[#303030] border-l-2 border-l-[#007acc] rounded p-2 text-[#cccccc] mt-1 text-xs animate-pulse">
                   <div className="flex items-center gap-2 mb-1">
                      <span className="animate-spin text-[#007acc]">↻</span> MCP Tool: {activeToolInfo.name}
                   </div>
                </div>
            )}

            {isTyping && activeTypingText && script.events[currentEventIdx]?.type === 'agent_output' && (
                <div className="text-[#cccccc] self-start w-full leading-relaxed whitespace-pre-wrap">
                    {activeTypingText}<span className="animate-pulse">|</span>
                </div>
            )}
        </div>

        {/* Chat Input Area */}
        <div className="p-4 border-t border-[#303030] bg-[#252526]">
            <div className="bg-[#3c3c3c] border border-[#454545] rounded-xl flex items-end p-2 pb-2 relative">
                <div className="text-[#cccccc] w-full min-h-[44px] px-2 py-1 flex items-center flex-wrap">
                    {isTyping && script.events[currentEventIdx]?.type === 'user_input' ? (
                        <>{activeTypingText}<span className="w-[2px] h-[1em] bg-[#cccccc] animate-pulse align-middle ml-[1px]"></span></>
                    ) : (
                        <span className="opacity-30">Ask the agent anything...</span>
                    )}
                </div>
                <button className="bg-[#007acc] text-white w-7 h-7 rounded-full flex items-center justify-center shrink-0 mb-1 absolute bottom-2 right-2 disabled:opacity-50" disabled>
                    ↑
                </button>
            </div>
        </div>
      </div>
    </div>
  );
}
