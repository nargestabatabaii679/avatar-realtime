import { useCallback, useRef, useState } from "react";

export interface AudioRecorderState {
  recording: boolean;
  audioBlob: Blob | null;
  durationSec: number;
  /** Normalised 0–1 frequency amplitudes (32 bars) for waveform display. */
  waveValues: number[];
}

export interface AudioRecorderActions {
  start: () => Promise<void>;
  stop: () => void;
  clear: () => void;
}

export type AudioRecorder = AudioRecorderState & AudioRecorderActions;

const WAVE_BARS = 32;

/**
 * Browser mic recording hook using MediaRecorder + Web Audio API.
 * Exposes real-time waveform data for visualisation.
 */
export function useAudioRecorder(): AudioRecorder {
  const [recording,   setRecording]   = useState(false);
  const [audioBlob,   setAudioBlob]   = useState<Blob | null>(null);
  const [durationSec, setDurationSec] = useState(0);
  const [waveValues,  setWaveValues]  = useState<number[]>(Array(WAVE_BARS).fill(0));

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef        = useRef<Blob[]>([]);
  const timerRef         = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const animFrameRef     = useRef<number | undefined>(undefined);

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // AudioContext may need sampleRate on some browsers — cast to avoid TS strict error
    const audioCtx = new (window.AudioContext ?? (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext)();
    const source   = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = WAVE_BARS * 2;
    source.connect(analyser);

    const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
    mediaRecorderRef.current = mr;
    chunksRef.current = [];

    mr.ondataavailable = (e) => chunksRef.current.push(e.data);
    mr.onstop = () => {
      setAudioBlob(new Blob(chunksRef.current, { type: "audio/webm" }));
      stream.getTracks().forEach((t) => t.stop());
      audioCtx.close();
    };

    mr.start(100);
    setRecording(true);
    setDurationSec(0);

    timerRef.current = setInterval(() => setDurationSec((s) => s + 1), 1000);

    const freqData = new Uint8Array(analyser.frequencyBinCount);
    const animate = () => {
      analyser.getByteFrequencyData(freqData);
      setWaveValues(Array.from(freqData).slice(0, WAVE_BARS).map((v) => v / 255));
      animFrameRef.current = requestAnimationFrame(animate);
    };
    animate();
  }, []);

  const stop = useCallback(() => {
    mediaRecorderRef.current?.stop();
    clearInterval(timerRef.current);
    cancelAnimationFrame(animFrameRef.current!);
    setRecording(false);
    setWaveValues(Array(WAVE_BARS).fill(0));
  }, []);

  const clear = useCallback(() => {
    setAudioBlob(null);
    setDurationSec(0);
  }, []);

  return { recording, audioBlob, durationSec, waveValues, start, stop, clear };
}
