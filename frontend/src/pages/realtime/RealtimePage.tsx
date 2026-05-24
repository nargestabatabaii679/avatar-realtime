import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Mic, MicOff, PhoneOff, MessageSquare, Wifi, WifiOff, Loader2 } from "lucide-react";
import { api } from "../../services/api";
import { useAuthStore } from "../../stores/authStore";
import { cn } from "../../utils/cn";

export default function RealtimePage() {
  const { t } = useTranslation();
  const { token } = useAuthStore();
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [transcript, setTranscript] = useState<Array<{role:string;text:string;ts:number}>>([]);
  const [latency, setLatency] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get("/agents").then((r) => r.data),
  });

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const connect = useCallback(async () => {
    if (isConnecting || isConnected) return;
    setIsConnecting(true);

    try {
      const wsUrl = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/api/v1/realtime/connect?token=${token}${selectedAgent ? `&agent_id=${selectedAgent}` : ""}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "connected") {
          setSessionId(msg.session_id);
        } else if (msg.type === "transcription" && msg.is_final) {
          setTranscript((t) => [...t, { role: "user", text: msg.text, ts: Date.now() }]);
        } else if (msg.type === "llm_chunk") {
          setTranscript((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [...prev.slice(0, -1), { ...last, text: last.text + msg.text }];
            }
            return [...prev, { role: "assistant", text: msg.text, ts: Date.now() }];
          });
        } else if (msg.type === "audio_chunk") {
          playAudioChunk(msg.data, msg.sample_rate || 24000);
        } else if (msg.type === "turn_complete") {
          setLatency(msg.latency_ms);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsConnecting(false);
        setSessionId(null);
      };

      ws.onerror = () => {
        setIsConnecting(false);
        setIsConnected(false);
      };

      // Start microphone
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = async (e) => {
        if (ws.readyState === WebSocket.OPEN && e.data.size > 0 && !isMuted) {
          const buffer = await e.data.arrayBuffer();
          const base64 = btoa(String.fromCharCode(...new Uint8Array(buffer)));
          ws.send(JSON.stringify({ type: "audio_chunk", data: base64 }));
        }
      };

      mediaRecorder.start(100); // 100ms chunks
    } catch (err) {
      setIsConnecting(false);
      console.error("Connection failed:", err);
    }
  }, [isConnecting, isConnected, token, selectedAgent, isMuted]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    mediaRecorderRef.current?.stop();
    wsRef.current = null;
    mediaRecorderRef.current = null;
    setIsConnected(false);
    setSessionId(null);
  }, []);

  const playAudioChunk = (base64Data: string, sampleRate: number) => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate });
      }
      const binary = atob(base64Data);
      const buffer = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) buffer[i] = binary.charCodeAt(i);
      audioContextRef.current.decodeAudioData(buffer.buffer).then((decoded) => {
        const source = audioContextRef.current!.createBufferSource();
        source.buffer = decoded;
        source.connect(audioContextRef.current!.destination);
        source.start();
      }).catch(() => {});
    } catch {}
  };

  const agentList = agents || [];
  const selectedAgentData = agentList.find((a: any) => a.id === selectedAgent);

  return (
    <div className="space-y-6 animate-fade-in h-full flex flex-col">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("nav.realtime")}</h1>
        <p className="text-muted-foreground text-sm mt-1">Real-time conversational AI avatar with &lt;1.2s latency</p>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Avatar Stream */}
        <div className="lg:col-span-2 bg-card border border-border rounded-2xl overflow-hidden flex flex-col min-h-[400px]">
          {/* Avatar display */}
          <div className="flex-1 bg-gradient-to-br from-slate-900 to-indigo-950 flex items-center justify-center relative">
            {selectedAgentData?.avatar_id ? (
              <div className="w-48 h-48 rounded-full overflow-hidden border-4 border-indigo-500/50 shadow-2xl">
                <div className="w-full h-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-6xl font-bold">
                  {selectedAgentData.name.charAt(0)}
                </div>
              </div>
            ) : (
              <div className="text-center text-white/60">
                <div className="w-32 h-32 rounded-full bg-white/10 flex items-center justify-center mx-auto mb-4">
                  <Mic size={40} className="opacity-50" />
                </div>
                <p className="text-sm">Select an agent to start</p>
              </div>
            )}

            {/* Status indicators */}
            <div className="absolute top-4 start-4 flex items-center gap-2">
              <div className={cn("flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
                isConnected ? "bg-green-500/20 text-green-400" : "bg-white/10 text-white/60"
              )}>
                {isConnected ? <Wifi size={12} /> : <WifiOff size={12} />}
                {isConnected ? "Live" : "Offline"}
              </div>
              {latency && (
                <div className="bg-white/10 text-white/70 px-2.5 py-1 rounded-full text-xs">
                  {latency}ms
                </div>
              )}
            </div>

            {/* Speaking animation */}
            {isConnected && !isMuted && (
              <div className="absolute bottom-6 flex items-end gap-1">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i}
                    className="w-1.5 bg-indigo-400 rounded-full animate-pulse"
                    style={{ height: Math.random() * 20 + 8, animationDelay: `${i * 100}ms` }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Controls */}
          <div className="p-4 bg-card/80 border-t border-border flex items-center justify-center gap-4">
            {!isConnected ? (
              <>
                <select
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  className="px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                >
                  <option value="">Select Agent (optional)</option>
                  {agentList.map((a: any) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
                <button
                  onClick={connect}
                  disabled={isConnecting}
                  className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-xl font-medium hover:opacity-90 disabled:opacity-50 transition-all"
                >
                  {isConnecting ? <Loader2 size={16} className="animate-spin" /> : <Mic size={16} />}
                  {isConnecting ? "Connecting…" : "Start Conversation"}
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => setIsMuted(!isMuted)}
                  className={cn(
                    "p-3 rounded-xl transition-colors",
                    isMuted ? "bg-red-500/20 text-red-400 hover:bg-red-500/30" : "bg-muted hover:bg-accent text-foreground"
                  )}
                >
                  {isMuted ? <MicOff size={20} /> : <Mic size={20} />}
                </button>
                <button
                  onClick={disconnect}
                  className="flex items-center gap-2 px-6 py-2.5 bg-red-500 text-white rounded-xl font-medium hover:bg-red-600 transition-colors"
                >
                  <PhoneOff size={16} />
                  End
                </button>
              </>
            )}
          </div>
        </div>

        {/* Transcript */}
        <div className="bg-card border border-border rounded-2xl flex flex-col min-h-[400px]">
          <div className="p-4 border-b border-border flex items-center gap-2">
            <MessageSquare size={16} className="text-muted-foreground" />
            <h3 className="font-semibold text-foreground text-sm">Conversation Transcript</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
            {transcript.length === 0 ? (
              <div className="text-center text-sm text-muted-foreground py-8">
                Conversation transcript will appear here
              </div>
            ) : transcript.map((msg, i) => (
              <div key={i} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                <div className={cn(
                  "max-w-[85%] px-3 py-2 rounded-xl text-sm",
                  msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"
                )}>
                  {msg.text}
                </div>
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
          {sessionId && (
            <div className="px-4 pb-3 text-xs text-muted-foreground">
              Session: {sessionId.slice(0, 8)}…
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
