import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, Plus, Trash2, MessageSquare, Send, Loader2 } from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";

const ROLES = ["teacher","doctor","museum_guide","sales_consultant","customer_support","receptionist","custom"];
const LLM_PROVIDERS = [{ value: "openai", label: "OpenAI GPT" }, { value: "deepseek", label: "DeepSeek" }, { value: "ollama", label: "Ollama (Local)" }];
const LLM_MODELS: Record<string, string[]> = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
  deepseek: ["deepseek-chat", "deepseek-coder"],
  ollama: ["llama3.1:70b", "qwen2.5:72b", "mistral:7b"],
};

export default function AgentBuilderPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [chatMessage, setChatMessage] = useState("");
  const [chatHistory, setChatHistory] = useState<Array<{role:string;content:string}>>([]);
  const [form, setForm] = useState({ name: "", role: "teacher", system_prompt: "", llm_provider: "openai", llm_model: "gpt-4o-mini", avatar_id: "", voice_model_id: "", knowledge_base_id: "" });

  const { data: agents } = useQuery({ queryKey: ["agents"], queryFn: () => api.get("/agents").then((r) => r.data) });
  const { data: avatars } = useQuery({ queryKey: ["avatars", "ready"], queryFn: () => api.get("/avatars?status=ready").then((r) => r.data) });
  const { data: voices } = useQuery({ queryKey: ["voices", "ready"], queryFn: () => api.get("/voices?status=ready").then((r) => r.data) });
  const { data: kbs } = useQuery({ queryKey: ["knowledge"], queryFn: () => api.get("/knowledge").then((r) => r.data) });

  const createMutation = useMutation({
    mutationFn: () => api.post("/agents", form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["agents"] }); setShowCreate(false); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/agents/${id}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["agents"] }); if (selectedAgent) setSelectedAgent(null); },
  });

  const chatMutation = useMutation({
    mutationFn: ({ agentId, message }: { agentId: string; message: string }) =>
      api.post(`/agents/${agentId}/chat`, { message }),
    onSuccess: (res, vars) => {
      setChatHistory((h) => [...h, { role: "user", content: vars.message }, { role: "assistant", content: res.data.response }]);
      setChatMessage("");
    },
  });

  const agentList = agents || [];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("agent.title")}</h1>
          <p className="text-muted-foreground text-sm mt-1">Build conversational AI agents with custom knowledge</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus size={16} /> {t("agent.create")}
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-fade-in">
            <h2 className="text-lg font-semibold text-foreground mb-4">Create AI Agent</h2>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Agent Name", field: "name", type: "text", placeholder: "Sales Assistant Leila" },
              ].map(({ label, field, type, placeholder }) => (
                <div key={field} className="col-span-2">
                  <label className="block text-sm font-medium text-foreground mb-1.5">{label}</label>
                  <input type={type} value={(form as any)[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                    placeholder={placeholder}
                    className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              ))}
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">{t("agent.role")}</label>
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                >
                  {ROLES.map((r) => <option key={r} value={r}>{r.replace(/_/g," ")}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">LLM Provider</label>
                <select value={form.llm_provider} onChange={(e) => setForm({ ...form, llm_provider: e.target.value, llm_model: LLM_MODELS[e.target.value][0] })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                >
                  {LLM_PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">LLM Model</label>
                <select value={form.llm_model} onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                >
                  {(LLM_MODELS[form.llm_provider] || []).map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Avatar (optional)</label>
                <select value={form.avatar_id} onChange={(e) => setForm({ ...form, avatar_id: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                >
                  <option value="">None</option>
                  {(avatars?.items || []).map((a: any) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Knowledge Base (optional)</label>
                <select value={form.knowledge_base_id} onChange={(e) => setForm({ ...form, knowledge_base_id: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                >
                  <option value="">None</option>
                  {(kbs || []).map((kb: any) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-foreground mb-1.5">{t("agent.systemPrompt")}</label>
                <textarea value={form.system_prompt} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  rows={4} placeholder="You are a helpful AI assistant named..."
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowCreate(false)} className="flex-1 py-2 px-4 border border-border rounded-lg text-sm hover:bg-accent transition-colors">{t("common.cancel")}</button>
              <button onClick={() => createMutation.mutate()} disabled={!form.name || createMutation.isPending}
                className="flex-1 py-2 px-4 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {createMutation.isPending ? "Creating…" : t("agent.create")}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agents List */}
        <div className="space-y-3">
          {agentList.length === 0 ? (
            <div className="text-center py-12 bg-card border border-border rounded-xl">
              <Bot size={40} className="mx-auto mb-3 text-muted-foreground opacity-40" />
              <p className="text-sm text-muted-foreground">{t("agent.noAgents")}</p>
            </div>
          ) : agentList.map((agent: any) => (
            <div key={agent.id}
              onClick={() => { setSelectedAgent(agent); setChatHistory([]); }}
              className={cn(
                "bg-card border rounded-xl p-4 cursor-pointer transition-all",
                selectedAgent?.id === agent.id ? "border-primary ring-1 ring-primary/30" : "border-border hover:border-primary/50"
              )}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center text-white font-bold text-sm">{agent.name.charAt(0)}</div>
                  <div>
                    <h3 className="font-medium text-foreground text-sm">{agent.name}</h3>
                    <p className="text-xs text-muted-foreground capitalize">{agent.role?.replace(/_/g," ")}</p>
                  </div>
                </div>
                <button onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(agent.id); }}
                  className="p-1.5 hover:bg-accent rounded-lg text-muted-foreground hover:text-red-500"
                ><Trash2 size={13} /></button>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                <MessageSquare size={12} />
                <span>{agent.conversation_count} conversations</span>
                <span>·</span>
                <span>{agent.llm_model}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Chat Interface */}
        {selectedAgent ? (
          <div className="lg:col-span-2 bg-card border border-border rounded-xl flex flex-col" style={{ height: 520 }}>
            <div className="p-4 border-b border-border flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center text-white text-sm font-bold">{selectedAgent.name.charAt(0)}</div>
              <div>
                <h3 className="font-semibold text-foreground text-sm">{selectedAgent.name}</h3>
                <p className="text-xs text-muted-foreground">{selectedAgent.llm_provider} · {selectedAgent.llm_model}</p>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
              {chatHistory.length === 0 && (
                <div className="text-center text-sm text-muted-foreground py-8">Start a conversation with {selectedAgent.name}</div>
              )}
              {chatHistory.map((msg, i) => (
                <div key={i} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                  <div className={cn("max-w-[80%] px-4 py-2 rounded-2xl text-sm", msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground")}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {chatMutation.isPending && (
                <div className="flex justify-start">
                  <div className="bg-muted px-4 py-2 rounded-2xl">
                    <Loader2 size={14} className="animate-spin text-muted-foreground" />
                  </div>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-border flex gap-2">
              <input value={chatMessage} onChange={(e) => setChatMessage(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && chatMessage.trim()) { chatMutation.mutate({ agentId: selectedAgent.id, message: chatMessage }); } }}
                placeholder="Type a message…"
                className="flex-1 px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                onClick={() => chatMessage.trim() && chatMutation.mutate({ agentId: selectedAgent.id, message: chatMessage })}
                disabled={!chatMessage.trim() || chatMutation.isPending}
                className="px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        ) : (
          <div className="lg:col-span-2 bg-card border border-border rounded-xl flex items-center justify-center text-muted-foreground text-sm">
            Select an agent to start chatting
          </div>
        )}
      </div>
    </div>
  );
}
