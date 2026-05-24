import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Plus, Upload, Globe, Search, Trash2, FileText, Loader2, Send } from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";

export default function KnowledgeCenterPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedKB, setSelectedKB] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showAddUrl, setShowAddUrl] = useState(false);
  const [kbName, setKbName] = useState("");
  const [kbDesc, setKbDesc] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [chatMsg, setChatMsg] = useState("");
  const [chatHistory, setChatHistory] = useState<Array<{role:string;content:string}>>([]);

  const { data: kbs } = useQuery({ queryKey: ["knowledge"], queryFn: () => api.get("/knowledge").then((r) => r.data) });
  const { data: docs } = useQuery({
    queryKey: ["knowledge", selectedKB?.id, "documents"],
    queryFn: () => api.get(`/knowledge/${selectedKB.id}/documents`).then((r) => r.data),
    enabled: !!selectedKB,
  });

  const createMutation = useMutation({
    mutationFn: () => api.post("/knowledge", { name: kbName, description: kbDesc }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["knowledge"] }); setShowCreate(false); setKbName(""); setKbDesc(""); },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData(); form.append("file", file);
      return api.post(`/knowledge/${selectedKB.id}/upload`, form, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge", selectedKB?.id, "documents"] }),
  });

  const urlMutation = useMutation({
    mutationFn: () => api.post(`/knowledge/${selectedKB.id}/add-url`, { url: urlInput, depth: 2 }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["knowledge", selectedKB?.id, "documents"] }); setShowAddUrl(false); setUrlInput(""); },
  });

  const searchMutation = useMutation({
    mutationFn: () => api.post(`/knowledge/${selectedKB.id}/search`, { query: searchQuery, top_k: 5 }),
    onSuccess: (res) => setSearchResults(res.data.results || []),
  });

  const chatMutation = useMutation({
    mutationFn: (msg: string) => api.post(`/knowledge/${selectedKB.id}/chat`, { message: msg, language: "fa" }),
    onSuccess: (res, msg) => {
      setChatHistory((h) => [...h, { role: "user", content: msg }, { role: "assistant", content: res.data.response }]);
      setChatMsg("");
    },
  });

  const onDrop = useCallback((files: File[]) => {
    if (selectedKB && files.length > 0) uploadMutation.mutate(files[0]);
  }, [selectedKB]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { "application/pdf": [".pdf"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"], "text/plain": [".txt"] }, multiple: false,
  });

  const kbList = kbs || [];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("knowledge.title")}</h1>
          <p className="text-muted-foreground text-sm mt-1">Upload documents and build RAG knowledge bases</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus size={16} /> {t("knowledge.createKB")}
        </button>
      </div>

      {/* Create KB Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-md animate-fade-in">
            <h2 className="text-lg font-semibold text-foreground mb-4">Create Knowledge Base</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Name</label>
                <input value={kbName} onChange={(e) => setKbName(e.target.value)} placeholder="Product Documentation"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Description</label>
                <textarea value={kbDesc} onChange={(e) => setKbDesc(e.target.value)} rows={2}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div className="flex gap-3">
                <button onClick={() => setShowCreate(false)} className="flex-1 py-2 border border-border rounded-lg text-sm hover:bg-accent transition-colors">{t("common.cancel")}</button>
                <button onClick={() => createMutation.mutate()} disabled={!kbName || createMutation.isPending}
                  className="flex-1 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {createMutation.isPending ? "Creating…" : t("common.create")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* KB List */}
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">Knowledge Bases</h2>
          {kbList.length === 0 ? (
            <div className="text-center py-8 bg-card border border-border rounded-xl">
              <BookOpen size={28} className="mx-auto mb-2 text-muted-foreground opacity-40" />
              <p className="text-xs text-muted-foreground">{t("knowledge.noKBs")}</p>
            </div>
          ) : kbList.map((kb: any) => (
            <button key={kb.id} onClick={() => { setSelectedKB(kb); setChatHistory([]); setSearchResults([]); }}
              className={cn(
                "w-full text-start p-3 rounded-xl border transition-all",
                selectedKB?.id === kb.id ? "border-primary bg-primary/5" : "border-border bg-card hover:border-primary/50"
              )}
            >
              <div className="flex items-center gap-2">
                <BookOpen size={14} className="text-primary shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{kb.name}</p>
                  <p className="text-xs text-muted-foreground">{kb.chunk_count || 0} chunks · {kb.document_count || 0} docs</p>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* KB Detail */}
        {selectedKB ? (
          <div className="lg:col-span-3 space-y-4">
            {/* Upload area */}
            <div className="bg-card border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-foreground">{selectedKB.name}</h3>
                <div className="flex gap-2">
                  <button onClick={() => setShowAddUrl(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-lg text-xs hover:bg-accent transition-colors"
                  ><Globe size={12} /> {t("knowledge.addUrl")}</button>
                </div>
              </div>

              {/* Add URL Modal */}
              {showAddUrl && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
                  <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-md animate-fade-in">
                    <h3 className="font-semibold text-foreground mb-4">Add Website URL</h3>
                    <input value={urlInput} onChange={(e) => setUrlInput(e.target.value)} placeholder="https://yoursite.com/docs"
                      className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none mb-4"
                    />
                    <div className="flex gap-3">
                      <button onClick={() => setShowAddUrl(false)} className="flex-1 py-2 border border-border rounded-lg text-sm hover:bg-accent transition-colors">{t("common.cancel")}</button>
                      <button onClick={() => urlMutation.mutate()} disabled={!urlInput || urlMutation.isPending}
                        className="flex-1 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                      >
                        {urlMutation.isPending ? "Adding…" : "Add URL"}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div {...getRootProps()} className={cn(
                "border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors",
                isDragActive ? "drop-zone-active" : "border-border hover:border-primary/50"
              )}>
                <input {...getInputProps()} />
                <Upload size={24} className="mx-auto mb-2 text-muted-foreground opacity-50" />
                <p className="text-sm font-medium text-foreground">{t("knowledge.uploadDoc")}</p>
                <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, PPTX, XLSX, TXT</p>
                {uploadMutation.isPending && <p className="text-xs text-primary mt-2">{t("knowledge.processing")}</p>}
              </div>

              {/* Document list */}
              {(docs || []).length > 0 && (
                <div className="mt-4 space-y-2">
                  {(docs || []).map((doc: any) => (
                    <div key={doc.id} className="flex items-center gap-3 p-3 rounded-lg bg-muted">
                      <FileText size={16} className="text-primary shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-foreground truncate">{doc.original_filename}</p>
                        <p className="text-xs text-muted-foreground">{doc.status} · {doc.chunk_count} chunks</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Search + Chat */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Semantic Search */}
              <div className="bg-card border border-border rounded-xl p-4">
                <h4 className="font-medium text-foreground mb-3 text-sm">{t("knowledge.search")}</h4>
                <div className="flex gap-2 mb-3">
                  <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && searchMutation.mutate()}
                    placeholder="Search your knowledge base…"
                    className="flex-1 px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                  />
                  <button onClick={() => searchMutation.mutate()} disabled={!searchQuery || searchMutation.isPending}
                    className="px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
                  >
                    <Search size={14} />
                  </button>
                </div>
                <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin">
                  {searchResults.map((r, i) => (
                    <div key={i} className="p-2 rounded-lg bg-muted text-xs">
                      <p className="text-foreground line-clamp-3">{r.text}</p>
                      <p className="text-muted-foreground mt-1">Score: {(r.score * 100).toFixed(0)}%</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Chat */}
              <div className="bg-card border border-border rounded-xl p-4 flex flex-col" style={{ minHeight: 280 }}>
                <h4 className="font-medium text-foreground mb-3 text-sm">{t("knowledge.chat")}</h4>
                <div className="flex-1 overflow-y-auto space-y-2 scrollbar-thin mb-3">
                  {chatHistory.map((msg, i) => (
                    <div key={i} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                      <div className={cn("max-w-[85%] px-3 py-2 rounded-xl text-xs", msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground")}>
                        {msg.content}
                      </div>
                    </div>
                  ))}
                  {chatMutation.isPending && <div className="flex justify-start"><div className="bg-muted px-3 py-2 rounded-xl"><Loader2 size={12} className="animate-spin text-muted-foreground" /></div></div>}
                </div>
                <div className="flex gap-2">
                  <input value={chatMsg} onChange={(e) => setChatMsg(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && chatMsg.trim() && chatMutation.mutate(chatMsg)}
                    placeholder="Ask a question…" className="flex-1 px-3 py-1.5 bg-muted border border-border rounded-lg text-xs text-foreground focus:outline-none"
                  />
                  <button onClick={() => chatMsg.trim() && chatMutation.mutate(chatMsg)} disabled={!chatMsg.trim() || chatMutation.isPending}
                    className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
                  >
                    <Send size={12} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="lg:col-span-3 bg-card border border-border rounded-xl flex items-center justify-center text-muted-foreground text-sm">
            Select a knowledge base or create one to get started
          </div>
        )}
      </div>
    </div>
  );
}
