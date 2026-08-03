"use client";

import { useState, useEffect, useCallback } from "react";
import "./admin.css";
import {
  Sliders,
  User,
  TextAa,
  Plus,
  Tag,
  X,
  Trash,
  Spinner,
  WarningCircle,
  ArrowsClockwise
} from "@phosphor-icons/react";

const APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwwudCW1hW9TbEV3btIXJl9rYi3GYU2E1jQ55mAXj9LAniuG8i0SLPMmrRrgWgsdHAQWA/exec";

interface KeywordData {
  keyword: string;
  sentiment: string;
  weight?: number;
}

export default function AdminDashboard() {
  const [keywords, setKeywords] = useState<KeywordData[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [showKeywordModal, setShowKeywordModal] = useState<boolean>(false);
  const [newKwWord, setNewKwWord] = useState("");
  const [newKwSentiment, setNewKwSentiment] = useState("negative");
  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(null);

  const fetchRemoteKeywords = useCallback(async () => {
    setIsLoading(true);
    setNetworkError(null);
    try {
      const res = await fetch(APPS_SCRIPT_URL, { method: "GET" });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status} - Google Apps Script returned an error.`);
      }
      const data = await res.json();
      if (Array.isArray(data)) {
        setKeywords(data);
      } else {
        throw new Error("Invalid response format from Google Apps Script.");
      }
    } catch (err: any) {
      console.error("Network error loading keywords:", err);
      setNetworkError(err?.message || "Failed to load keywords. Network connection or endpoint error.");
      setKeywords([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRemoteKeywords();
  }, [fetchRemoteKeywords]);

  const autoSave = useCallback(async (updatedList: KeywordData[]) => {
    setIsSaving(true);
    setNetworkError(null);
    try {
      const payload = encodeURIComponent(JSON.stringify(updatedList));
      const res = await fetch(`${APPS_SCRIPT_URL}?action=save&data=${payload}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status} failed to save data.`);
      }
      setSaveSuccessMessage("Successfully saved to Google Sheets");
      setTimeout(() => setSaveSuccessMessage(null), 3500);
    } catch (err: any) {
      setNetworkError("Failed to save changes to Google Sheets. Network error.");
    } finally {
      setIsSaving(false);
    }
  }, []);

  const handleAddKeyword = useCallback(async () => {
    if (!newKwWord.trim()) return;
    const kwObj: KeywordData = {
      keyword: newKwWord.trim().toLowerCase(),
      sentiment: newKwSentiment,
      weight: 50,
    };
    const updated = [...keywords, kwObj];
    setKeywords(updated);
    setNewKwWord("");
    setShowKeywordModal(false);
    autoSave(updated);
  }, [newKwWord, newKwSentiment, keywords, autoSave]);

  const handleRemoveKeyword = useCallback((index: number) => {
    const updated = [...keywords];
    updated.splice(index, 1);
    setKeywords(updated);
    autoSave(updated);
  }, [keywords, autoSave]);

  return (
    <div className="admin-container">
      <header className="admin-header">
        <div className="admin-header-inner">
          <div className="admin-brand">
            <div className="admin-brand-icon">
              <Sliders size={22} weight="bold" />
            </div>
            <div>
              <h1 className="admin-title">Supervisor Configuration Dashboard</h1>
              <p className="admin-subtitle">
                Manage monitored keywords and target sentiment categories.
              </p>
            </div>
          </div>
          <div className="admin-user-profile">
            <div className="admin-user-info">
              <div className="admin-user-name">Sarah Jenkins</div>
              <div className="admin-user-role">Supervisor • Team Alpha</div>
            </div>
            <div className="admin-avatar-badge">
              <User size={18} weight="bold" />
            </div>
          </div>
        </div>
      </header>

      <main className="admin-main">
        {saveSuccessMessage && (
          <div style={{ backgroundColor: '#10b981', color: '#fff', padding: '0.85rem 1.25rem', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', fontWeight: 700 }}>
            <span>{saveSuccessMessage}</span>
            <button onClick={() => setSaveSuccessMessage(null)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
              <X size={16} />
            </button>
          </div>
        )}

        {networkError && (
          <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '1rem 1.25rem', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', fontWeight: 600 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <WarningCircle size={20} style={{ color: '#ef4444' }} />
              <span>Network Error: {networkError}</span>
            </div>
            <button
              onClick={fetchRemoteKeywords}
              style={{ backgroundColor: '#ffffff', border: '1px solid #fecaca', color: '#b91c1c', padding: '0.35rem 0.75rem', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
            >
              <ArrowsClockwise size={14} /> Retry Connection
            </button>
          </div>
        )}

        <section className="admin-section">
          <div className="admin-section-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h2 className="admin-section-title">
                <TextAa size={20} style={{ color: '#64748b' }} /> Monitored Target Keywords
              </h2>
              {isSaving && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.72rem', color: '#ff5722', fontWeight: 600 }}>
                  <Spinner size={14} className="animate-spin" /> Saving...
                </div>
              )}
            </div>
            <button onClick={() => setShowKeywordModal(true)} className="btn-secondary">
              <Plus size={16} style={{ color: '#ff5722' }} /> Add Keyword
            </button>
          </div>

          <div className="admin-section-body">
            <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '1.5rem', fontWeight: 500 }}>
              Configure target keywords for real-time phrase detection and highlighting during call monitoring.
            </p>

            {isLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3rem 1rem', color: '#64748b', gap: '0.5rem' }}>
                <Spinner size={24} className="animate-spin" style={{ color: '#ff5722' }} />
                <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Loading keywords from Google Sheets...</span>
              </div>
            ) : keywords.length > 0 ? (
              <div className="keywords-grid">
                {keywords.map((kw, idx) => (
                  <div key={idx} className="keyword-card">
                    <div className="keyword-card-top">
                      <span className={`keyword-badge ${kw.sentiment === 'negative' ? 'badge-neg' : 'badge-pos'}`}>
                        {kw.keyword}
                      </span>
                      <div style={{ display: 'flex', gap: '0.25rem' }}>
                        <button onClick={() => handleRemoveKeyword(idx)} className="action-icon-btn delete" title="Delete Keyword">
                          <Trash size={14} />
                        </button>
                      </div>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '0.5rem', fontWeight: 600 }}>
                      Classification: <span style={{ color: kw.sentiment === 'negative' ? '#dc2626' : '#059669', textTransform: 'capitalize' }}>{kw.sentiment}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              !networkError && (
                <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.8rem' }}>
                  No keywords configured in Google Sheets. Click <strong>Add Keyword</strong> to add one.
                </div>
              )
            )}
          </div>
        </section>
      </main>

      {showKeywordModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3 style={{ fontSize: '0.85rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Tag size={18} style={{ color: '#ff5722' }} /> Add Monitored Keyword
              </h3>
              <button onClick={() => setShowKeywordModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Keyword or Phrase</label>
                <input
                  type="text"
                  value={newKwWord}
                  onChange={(e) => setNewKwWord(e.target.value)}
                  placeholder="e.g. cancel account"
                  className="form-control"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Sentiment Category</label>
                <div style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="sentiment"
                      value="positive"
                      checked={newKwSentiment === "positive"}
                      onChange={() => setNewKwSentiment("positive")}
                      style={{ accentColor: '#10b981' }}
                    />
                    Positive (Green)
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="sentiment"
                      value="negative"
                      checked={newKwSentiment === "negative"}
                      onChange={() => setNewKwSentiment("negative")}
                      style={{ accentColor: '#ef4444' }}
                    />
                    Negative (Red)
                  </label>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowKeywordModal(false)} className="btn-secondary">
                Cancel
              </button>
              <button onClick={handleAddKeyword} className="btn-primary">
                Add Keyword
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
