import { useState, useId } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  horizontalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Plus, Trash2, Sparkles, GripVertical, Clock, Send, Image as ImgIcon,
  Film, ChevronRight, LayoutTemplate,
} from "lucide-react";
import { cn } from "../../utils/cn";

interface Scene {
  id: string;
  number: number;
  script: string;
  duration: number;
  imagePrompt: string;
  showPromptInput: boolean;
  imagePlaceholder: string;
}

const DURATION_OPTIONS = [5, 10, 15, 20, 30, 45, 60];

const PLACEHOLDERS = [
  "🌅", "🏙️", "🎬", "🌿", "🔬", "🤝", "🚀", "🎨",
];

function SortableSceneCard({
  scene,
  onUpdate,
  onDelete,
}: {
  scene: Scene;
  onUpdate: (id: string, updates: Partial<Scene>) => void;
  onDelete: (id: string) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: scene.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 100 : undefined,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "card-premium p-0 w-64 shrink-0 flex flex-col overflow-hidden transition-all duration-200",
        isDragging && "opacity-75 scale-105 shadow-2xl ring-2 ring-primary/50"
      )}
    >
      {/* Card header */}
      <div className="flex items-center justify-between px-3 py-2.5 bg-muted/50 border-b border-border">
        <div className="flex items-center gap-2">
          <button
            {...attributes}
            {...listeners}
            className="text-muted-foreground hover:text-foreground cursor-grab active:cursor-grabbing transition-colors p-0.5"
          >
            <GripVertical size={14} />
          </button>
          <span className="text-xs font-bold text-muted-foreground">
            صحنه {scene.number}
          </span>
        </div>
        <button
          onClick={() => onDelete(scene.id)}
          className="p-1 rounded-lg hover:bg-red-500/10 text-muted-foreground hover:text-red-500 transition-colors"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {/* Image preview */}
      <div className="relative w-full h-36 bg-gradient-to-br from-muted to-muted/50 flex items-center justify-center overflow-hidden">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <span className="text-4xl">{scene.imagePlaceholder}</span>
          <span className="text-[10px]">پیش‌نمایش تصویر</span>
        </div>
        {/* AI image generation button */}
        <button
          onClick={() => onUpdate(scene.id, { showPromptInput: !scene.showPromptInput })}
          className="absolute bottom-2 left-2 flex items-center gap-1 px-2 py-1 rounded-lg bg-black/60 backdrop-blur-sm text-white text-[10px] font-medium hover:bg-black/80 transition-colors"
        >
          <Sparkles size={10} />
          تولید تصویر با AI
        </button>
      </div>

      {/* AI prompt input (inline, collapsible) */}
      {scene.showPromptInput && (
        <div className="px-3 py-2 border-b border-border bg-primary/5 animate-fade-in">
          <p className="text-[10px] text-primary font-semibold mb-1.5 flex items-center gap-1">
            <Sparkles size={10} /> توضیح تصویر برای AI
          </p>
          <div className="flex gap-1.5">
            <input
              value={scene.imagePrompt}
              onChange={(e) => onUpdate(scene.id, { imagePrompt: e.target.value })}
              placeholder="مثلاً: یک دفتر مدرن با نور طبیعی..."
              className="input-field text-[11px] py-1.5 flex-1"
              dir="rtl"
            />
            <button
              className="px-2.5 py-1.5 rounded-lg text-white text-[10px] font-bold transition-all"
              style={{ background: "var(--gradient-primary)" }}
            >
              ساخت
            </button>
          </div>
        </div>
      )}

      {/* Script textarea */}
      <div className="px-3 pt-3 pb-2">
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-1.5 block">
          متن گفتار
        </label>
        <textarea
          value={scene.script}
          onChange={(e) => onUpdate(scene.id, { script: e.target.value })}
          placeholder="توضیح صحنه را بنویسید..."
          className="w-full h-20 px-3 py-2 bg-muted border border-border rounded-xl text-foreground text-xs resize-none focus:outline-none focus:ring-2 focus:ring-primary/50 placeholder:text-muted-foreground/40 leading-relaxed"
          dir="rtl"
        />
      </div>

      {/* Duration selector */}
      <div className="px-3 pb-3">
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1">
          <Clock size={10} /> مدت زمان
        </label>
        <select
          value={scene.duration}
          onChange={(e) => onUpdate(scene.id, { duration: parseInt(e.target.value) })}
          className="input-field text-xs py-1.5"
          dir="rtl"
        >
          {DURATION_OPTIONS.map((d) => (
            <option key={d} value={d}>
              {d} ثانیه
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

let sceneCounter = 0;
function createScene(number: number): Scene {
  sceneCounter++;
  return {
    id: `scene-${Date.now()}-${sceneCounter}`,
    number,
    script: "",
    duration: 10,
    imagePrompt: "",
    showPromptInput: false,
    imagePlaceholder: PLACEHOLDERS[Math.floor(Math.random() * PLACEHOLDERS.length)],
  };
}

/* Pipeline flow step */
function PipelineStep({ emoji, label, isLast }: { emoji: string; label: string; isLast?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex flex-col items-center gap-1">
        <div className="w-10 h-10 rounded-xl bg-card border border-border flex items-center justify-center text-xl shadow-sm">
          {emoji}
        </div>
        <span className="text-[10px] font-semibold text-muted-foreground">{label}</span>
      </div>
      {!isLast && (
        <ChevronRight size={16} className="text-muted-foreground/40 mb-4 mx-1" />
      )}
    </div>
  );
}

export default function StoryboardPage() {
  const dndId = useId();
  const [scenes, setScenes] = useState<Scene[]>([createScene(1)]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const addScene = () => {
    setScenes((prev) => [...prev, createScene(prev.length + 1)]);
  };

  const updateScene = (id: string, updates: Partial<Scene>) => {
    setScenes((prev) =>
      prev.map((s) => (s.id === id ? { ...s, ...updates } : s))
    );
  };

  const deleteScene = (id: string) => {
    setScenes((prev) => {
      const next = prev.filter((s) => s.id !== id);
      return next.map((s, i) => ({ ...s, number: i + 1 }));
    });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setScenes((prev) => {
        const oldIdx = prev.findIndex((s) => s.id === active.id);
        const newIdx = prev.findIndex((s) => s.id === over.id);
        const reordered = arrayMove(prev, oldIdx, newIdx);
        return reordered.map((s, i) => ({ ...s, number: i + 1 }));
      });
    }
  };

  const totalDuration = scenes.reduce((acc, s) => acc + s.duration, 0);

  return (
    <div dir="rtl" className="flex flex-col gap-6 pb-8 animate-fade-in">

      {/* ═══ PAGE HEADER ═══════════════════════════════════════════ */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary)" }}
            >
              <LayoutTemplate size={18} className="text-white" />
            </div>
            <h1 className="text-xl font-bold text-foreground">استودیو استوری‌برد</h1>
          </div>
          <p className="text-sm text-muted-foreground mr-13">
            صحنه‌های ویدیو را طراحی و سازماندهی کنید
          </p>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="badge badge-primary text-xs px-2.5 py-1">
            {scenes.length} صحنه
          </span>
          {totalDuration > 0 && (
            <span className="badge badge-info text-xs px-2.5 py-1 flex items-center gap-1">
              <Clock size={10} />
              {Math.floor(totalDuration / 60) > 0
                ? `${Math.floor(totalDuration / 60)}:${(totalDuration % 60).toString().padStart(2, "0")}`
                : `${totalDuration} ثانیه`}
            </span>
          )}
          <button onClick={addScene} className="btn-secondary text-xs py-2 px-3 flex items-center gap-1.5">
            <Plus size={13} />
            اضافه کردن صحنه
          </button>
          <button
            className="btn-primary text-xs py-2 px-3 flex items-center gap-1.5"
            disabled={scenes.length === 0}
          >
            <Send size={13} />
            ارسال به ویدیو استودیو
          </button>
        </div>
      </div>

      {/* ═══ PIPELINE FLOW ════════════════════════════════════════ */}
      <div className="card-premium px-6 py-4">
        <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-4">
          جریان تولید محتوا
        </p>
        <div className="flex items-center gap-1 flex-wrap">
          <PipelineStep emoji="🖼️" label="تصویر" />
          <PipelineStep emoji="🎬" label="استوری‌برد" />
          <PipelineStep emoji="📹" label="ویدیو" />
          <PipelineStep emoji="📤" label="انتشار" isLast />
        </div>
      </div>

      {/* ═══ SCENES AREA ══════════════════════════════════════════ */}
      {scenes.length === 0 ? (
        /* Empty state */
        <div className="card-premium flex flex-col items-center justify-center py-20 gap-4 animate-fade-in-up">
          <div className="w-20 h-20 rounded-2xl border-2 border-dashed border-border flex items-center justify-center">
            <Film size={32} className="text-muted-foreground/30" />
          </div>
          <div className="text-center">
            <p className="text-foreground font-semibold mb-1">هنوز صحنه‌ای وجود ندارد</p>
            <p className="text-sm text-muted-foreground">
              برای شروع، یک صحنه اضافه کنید
            </p>
          </div>
          <button onClick={addScene} className="btn-primary px-6 py-2.5 flex items-center gap-2">
            <Plus size={16} />
            اولین صحنه را اضافه کنید
          </button>
        </div>
      ) : (
        <DndContext
          id={dndId}
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={scenes.map((s) => s.id)}
            strategy={horizontalListSortingStrategy}
          >
            <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-thin">
              {scenes.map((scene) => (
                <SortableSceneCard
                  key={scene.id}
                  scene={scene}
                  onUpdate={updateScene}
                  onDelete={deleteScene}
                />
              ))}

              {/* Add scene card */}
              <button
                onClick={addScene}
                className="w-64 shrink-0 rounded-2xl border-2 border-dashed border-border hover:border-primary/50 flex flex-col items-center justify-center gap-2 text-muted-foreground hover:text-primary transition-all duration-200 min-h-[360px] group"
              >
                <div className="w-12 h-12 rounded-xl border-2 border-dashed border-current flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Plus size={20} />
                </div>
                <span className="text-sm font-medium">صحنه جدید</span>
              </button>
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* ═══ SUMMARY BAR ═══════════════════════════════════════════ */}
      {scenes.length > 0 && (
        <div className="card-premium px-5 py-3 flex items-center justify-between flex-wrap gap-3 animate-fade-in">
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <ImgIcon size={14} className="text-primary" />
              <strong className="text-foreground">{scenes.length}</strong> صحنه
            </span>
            <span className="flex items-center gap-1.5">
              <Clock size={14} className="text-primary" />
              مجموع: <strong className="text-foreground">{totalDuration} ثانیه</strong>
            </span>
            <span className="flex items-center gap-1.5">
              <Film size={14} className="text-primary" />
              کلمات:{" "}
              <strong className="text-foreground">
                {scenes.reduce(
                  (acc, s) =>
                    acc + (s.script.trim() ? s.script.trim().split(/\s+/).length : 0),
                  0
                )}
              </strong>
            </span>
          </div>
          <button
            className="btn-primary text-sm py-2.5 px-5 flex items-center gap-2"
            disabled={scenes.length === 0}
          >
            <Send size={14} />
            ارسال به ویدیو استودیو
          </button>
        </div>
      )}
    </div>
  );
}
