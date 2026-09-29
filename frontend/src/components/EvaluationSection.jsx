import React, { useState, useEffect } from 'react';
import {
  FlaskConical,
  Play,
  Layers,
  Sparkles,
  Database,
  Clock,
  Cpu,
  CheckCircle2,
  XCircle,
  TrendingDown,
  RefreshCw,
  ChevronRight,
  Download,
  Eye,
  X,
  Copy,
  Check,
  Terminal,
  Activity,
} from 'lucide-react';
import {
  getBenchmarks,
  runPairedEvaluation,
  getRecentExperiments,
  getExportCsvUrl,
  getExperimentSummary,
  getExperimentEvents,
} from '../services/evaluationService';

export const EvaluationSection = ({ onLoadBenchmarkCode }) => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [selectedBugId, setSelectedBugId] = useState('B001');
  const [isRunning, setIsRunning] = useState(false);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [evalError, setEvalError] = useState(null);
  const [recentExperiments, setRecentExperiments] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Inspection states
  const [selectedEvaluationId, setSelectedEvaluationId] = useState(null);
  const [inspectionSummary, setInspectionSummary] = useState(null);
  const [inspectionEvents, setInspectionEvents] = useState([]);
  const [isLoadingInspection, setIsLoadingInspection] = useState(false);
  const [activeInspectTab, setActiveInspectTab] = useState('summary');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchBenchmarks();
    fetchHistory();
  }, []);

  const fetchBenchmarks = async () => {
    try {
      const data = await getBenchmarks();
      setBenchmarks(data);
      if (data.length > 0 && !selectedBugId) {
        setSelectedBugId(data[0].bug_id);
      }
    } catch (err) {
      console.error('Failed to load benchmarks:', err);
    }
  };

  const fetchHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const data = await getRecentExperiments(30);
      setRecentExperiments(data);
    } catch (err) {
      console.error('Failed to load experiments history:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleRunPaired = async () => {
    setIsRunning(true);
    setEvalError(null);
    try {
      const res = await runPairedEvaluation({ bugId: selectedBugId });
      setComparisonResult(res);
      fetchHistory();
      // Automatically load the inspection for the newly completed evaluation
      if (res && res.evaluation_id) {
        handleInspectEvaluation(res.evaluation_id);
      }
    } catch (err) {
      setEvalError(err.response?.data?.detail || err.message || 'Evaluation failed to complete.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleInspectEvaluation = async (evalId) => {
    if (!evalId || evalId === '-') return;
    setSelectedEvaluationId(evalId);
    setIsLoadingInspection(true);
    try {
      const [sumRes, evRes] = await Promise.allSettled([
        getExperimentSummary(evalId),
        getExperimentEvents(evalId),
      ]);
      setInspectionSummary(sumRes.status === 'fulfilled' ? sumRes.value : null);
      setInspectionEvents(evRes.status === 'fulfilled' ? evRes.value : []);
    } catch (err) {
      console.error('Failed to load evaluation inspection:', err);
    } finally {
      setIsLoadingInspection(false);
    }
  };

  const handleCopyId = (id) => {
    if (!id) return;
    navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const selectedBench = benchmarks.find((b) => b.bug_id === selectedBugId);

  return (
    <div className="evaluation-container">
      {/* 1. Page Header */}
      <div className="evaluation-header">
        <div className="evaluation-header-left">
          <FlaskConical size={20} className="text-accent" />
          <div>
            <h3 className="evaluation-title">Benchmark Evaluation & Baseline Comparison</h3>
            <p className="evaluation-subtitle">
              Evaluating <strong>Baseline (Full Context)</strong> vs <strong>Dynamic (Curated Context via MCP)</strong> on controlled benchmarks
            </p>
          </div>
        </div>
        <div className="evaluation-header-actions">
          <a
            href={getExportCsvUrl()}
            download="m8_experiments.csv"
            className="action-btn export-csv-btn"
            title="Download full evaluation dataset (CSV)"
          >
            <Download size={14} />
            <span>Export CSV</span>
          </a>
          <button
            type="button"
            className="history-refresh-btn"
            onClick={fetchHistory}
            title="Refresh experiment records"
          >
            <RefreshCw size={14} className={isLoadingHistory ? 'spin-icon' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 2. Experiment Controls / Benchmark Picker */}
      <div className="eval-toolbar">
        <div className="benchmark-picker">
          <label htmlFor="benchmark-select" className="eval-label">Benchmark Task:</label>
          <select
            id="benchmark-select"
            className="benchmark-dropdown"
            value={selectedBugId}
            onChange={(e) => setSelectedBugId(e.target.value)}
            disabled={isRunning}
          >
            {benchmarks.map((b) => (
              <option key={b.bug_id} value={b.bug_id}>
                {b.bug_id}: {b.title} ({b.expected_error})
              </option>
            ))}
          </select>
        </div>

        {selectedBench && onLoadBenchmarkCode && (
          <button
            type="button"
            className="action-btn secondary-btn load-code-btn"
            onClick={() => onLoadBenchmarkCode(selectedBench.code, selectedBench.language)}
            title="Load this benchmark code into the editor"
          >
            <ChevronRight size={14} />
            <span>Load Code into Editor</span>
          </button>
        )}

        <button
          type="button"
          className="action-btn primary-btn run-eval-btn"
          onClick={handleRunPaired}
          disabled={isRunning}
        >
          {isRunning ? (
            <>
              <RefreshCw size={14} className="spin-icon" />
              <span>Evaluating Paired Runs...</span>
            </>
          ) : (
            <>
              <Play size={14} />
              <span>Run Paired Evaluation</span>
            </>
          )}
        </button>
      </div>

      {/* Loading state indicator */}
      {isRunning && (
        <div className="eval-running-banner">
          <RefreshCw size={16} className="spin-icon" />
          <div className="eval-running-text">
            <strong>Evaluation in progress...</strong>
            <span>Executing paired experiments (Baseline vs Dynamic via MCP) on benchmark {selectedBugId}. Telemetry is streaming to backend.</span>
          </div>
        </div>
      )}

      {/* 3. Selected Benchmark Information */}
      {selectedBench && (
        <div className="benchmark-card">
          <div className="bench-meta">
            <span className="badge category-badge">{selectedBench.category}</span>
            <span className="badge error-badge">{selectedBench.expected_error}</span>
            <span className="badge lang-badge">{selectedBench.language}</span>
          </div>
          <p className="bench-desc">{selectedBench.description}</p>
        </div>
      )}

      {evalError && (
        <div className="eval-error-banner">
          <XCircle size={16} />
          <span>{evalError}</span>
        </div>
      )}

      {/* 4. Baseline vs Dynamic Side-by-Side Comparison */}
      {comparisonResult && (
        <div className="comparison-card">
          <div className="comparison-card-header">
            <div>
              <h4>Experimental Comparison — Benchmark {comparisonResult.bug_id}</h4>
              <span className="text-xs text-muted font-mono">Evaluation ID: {comparisonResult.evaluation_id}</span>
            </div>
            <div className="comparison-header-actions">
              <button
                type="button"
                className="action-btn inspect-eval-btn"
                onClick={() => handleInspectEvaluation(comparisonResult.evaluation_id)}
                title="Inspect detailed artifacts and event logs"
              >
                <Eye size={13} />
                <span>Inspect Artifacts</span>
              </button>
              <div className="reduction-pill">
                <TrendingDown size={14} />
                <span>
                  Context Reduction:{' '}
                  {comparisonResult.context_reduction_percent !== null
                    ? `${comparisonResult.context_reduction_percent}%`
                    : 'N/A'}
                </span>
              </div>
            </div>
          </div>

          <div className="comparison-kpi-grid">
            <div className="kpi-card highlight-kpi">
              <span className="kpi-label">Context Reduction</span>
              <div className="kpi-value text-reduction">
                {comparisonResult.context_reduction_percent !== null
                  ? `-${comparisonResult.context_reduction_percent}%`
                  : 'N/A'}
              </div>
              <span className="kpi-sub">
                {(comparisonResult.dynamic.context_chars ?? 0).toLocaleString()} vs {(comparisonResult.baseline.context_chars ?? 0).toLocaleString()} chars
              </span>
            </div>

            <div className="kpi-card">
              <span className="kpi-label">Token Savings</span>
              <div className="kpi-value">
                {comparisonResult.token_reduction_percent !== null
                  ? `-${comparisonResult.token_reduction_percent}%`
                  : 'N/A'}
              </div>
              <span className="kpi-sub">
                {comparisonResult.dynamic.token_usage_available && comparisonResult.dynamic.total_tokens !== null
                  ? `${comparisonResult.dynamic.total_tokens.toLocaleString()} tokens`
                  : 'Tokens tracked on OpenRouter'}
              </span>
            </div>

            <div className="kpi-card">
              <span className="kpi-label">Targeted MCP Calls</span>
              <div className="kpi-value text-accent">
                {comparisonResult.dynamic.mcp_calls}
              </div>
              <span className="kpi-sub">Selective runtime state queries</span>
            </div>

            <div className="kpi-card">
              <span className="kpi-label">Repair Correctness</span>
              <div className="kpi-value">
                {comparisonResult.dynamic.fix_correct ? (
                  <span className="text-success flex-row items-center gap-1">
                    <CheckCircle2 size={16} /> Validated
                  </span>
                ) : comparisonResult.dynamic.re_execution_passed ? (
                  <span className="text-warning flex-row items-center gap-1">
                    Passed (Exit 0)
                  </span>
                ) : (
                  <span className="text-error flex-row items-center gap-1">
                    <XCircle size={16} /> Needs Review
                  </span>
                )}
              </div>
              <span className="kpi-sub">Re-execution & semantic validation</span>
            </div>
          </div>

          <div className="comparison-table-wrapper">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Evaluation Metric</th>
                  <th className="th-baseline">Baseline (Full Context)</th>
                  <th className="th-dynamic">Dynamic (Curated Context)</th>
                  <th className="th-diff">Difference / Observation</th>
                </tr>
              </thead>
              <tbody>
                <tr className="table-group-header">
                  <td colSpan={4}>Context & Token Consumption</td>
                </tr>
                <tr>
                  <td className="metric-name">Status</td>
                  <td>
                    <span className={`outcome-pill ${comparisonResult.baseline.status === 'completed' ? 'success' : 'failure'}`}>
                      {comparisonResult.baseline.status === 'completed' ? 'Completed' : comparisonResult.baseline.status}
                    </span>
                  </td>
                  <td>
                    <span className={`outcome-pill ${comparisonResult.dynamic.status === 'completed' ? 'success' : 'failure'}`}>
                      {comparisonResult.dynamic.status === 'completed' ? 'Completed' : comparisonResult.dynamic.status}
                    </span>
                  </td>
                  <td>Run execution status</td>
                </tr>
                <tr>
                  <td className="metric-name">Context Size (chars)</td>
                  <td>{(comparisonResult.baseline.context_chars ?? comparisonResult.baseline.context_size ?? 0).toLocaleString()} chars</td>
                  <td>{(comparisonResult.dynamic.context_chars ?? comparisonResult.dynamic.context_size ?? 0).toLocaleString()} chars</td>
                  <td className="text-reduction">
                    {comparisonResult.context_reduction_percent !== null
                      ? `${comparisonResult.context_reduction_percent}% fewer context characters`
                      : 'N/A'}
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">Input Tokens (tokens)</td>
                  <td>
                    {comparisonResult.baseline.token_usage_available && comparisonResult.baseline.input_tokens !== null
                      ? `${comparisonResult.baseline.input_tokens.toLocaleString()} tokens`
                      : 'N/A — token usage unavailable'}
                  </td>
                  <td>
                    {comparisonResult.dynamic.token_usage_available && comparisonResult.dynamic.input_tokens !== null
                      ? `${comparisonResult.dynamic.input_tokens.toLocaleString()} tokens`
                      : 'N/A — token usage unavailable'}
                  </td>
                  <td>Prompt token consumption</td>
                </tr>
                <tr>
                  <td className="metric-name">Output Tokens (tokens)</td>
                  <td>
                    {comparisonResult.baseline.token_usage_available && comparisonResult.baseline.output_tokens !== null
                      ? `${comparisonResult.baseline.output_tokens.toLocaleString()} tokens`
                      : 'N/A — token usage unavailable'}
                  </td>
                  <td>
                    {comparisonResult.dynamic.token_usage_available && comparisonResult.dynamic.output_tokens !== null
                      ? `${comparisonResult.dynamic.output_tokens.toLocaleString()} tokens`
                      : 'N/A — token usage unavailable'}
                  </td>
                  <td>Completion token consumption</td>
                </tr>
                <tr>
                  <td className="metric-name">Total Tokens (tokens)</td>
                  <td>
                    {comparisonResult.baseline.token_usage_available && comparisonResult.baseline.total_tokens !== null
                      ? `${comparisonResult.baseline.total_tokens.toLocaleString()} tokens`
                      : 'N/A — token usage unavailable'}
                  </td>
                  <td>
                    {comparisonResult.dynamic.token_usage_available && comparisonResult.dynamic.total_tokens !== null
                      ? `${comparisonResult.dynamic.total_tokens.toLocaleString()} tokens (Curator: ${comparisonResult.dynamic.curator_total_tokens ?? 0}, Debugger: ${comparisonResult.dynamic.debugger_total_tokens ?? 0})`
                      : 'N/A — token usage unavailable'}
                  </td>
                  <td>
                    {comparisonResult.token_reduction_percent !== null
                      ? `${comparisonResult.token_reduction_percent}% fewer total tokens`
                      : 'N/A (provider metadata unavailable)'}
                  </td>
                </tr>
                <tr className="table-group-header">
                  <td colSpan={4}>Selective Retrieval & Agent Operations</td>
                </tr>
                <tr>
                  <td className="metric-name">LLM Calls</td>
                  <td>{comparisonResult.baseline.llm_calls} call</td>
                  <td>{comparisonResult.dynamic.llm_calls} calls</td>
                  <td>
                    {comparisonResult.dynamic.llm_calls > comparisonResult.baseline.llm_calls
                      ? `+${comparisonResult.dynamic.llm_calls - comparisonResult.baseline.llm_calls} call (Curator step)`
                      : 'Identical count'}
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">MCP Tool Calls</td>
                  <td>0 calls (Direct Context)</td>
                  <td>{comparisonResult.dynamic.mcp_calls} calls (Selective Retrieval)</td>
                  <td>Dynamic query via MCP server</td>
                </tr>
                <tr className="table-group-header">
                  <td colSpan={4}>Latency & Execution Timing</td>
                </tr>
                <tr>
                  <td className="metric-name">LLM Time (ms)</td>
                  <td>{comparisonResult.baseline.llm_time_ms.toFixed(1)} ms</td>
                  <td>{comparisonResult.dynamic.llm_time_ms.toFixed(1)} ms</td>
                  <td>Total model query duration</td>
                </tr>
                <tr>
                  <td className="metric-name">MCP Query Time (ms)</td>
                  <td>0.0 ms</td>
                  <td>{comparisonResult.dynamic.mcp_query_time_ms.toFixed(1)} ms</td>
                  <td>Isolated MCP tool execution</td>
                </tr>
                <tr>
                  <td className="metric-name">MCP Transport Time (ms)</td>
                  <td>0.0 ms</td>
                  <td>{comparisonResult.dynamic.mcp_transport_time_ms.toFixed(1)} ms</td>
                  <td>MCP client transport/session overhead</td>
                </tr>
                <tr>
                  <td className="metric-name">MCP Total Time (ms)</td>
                  <td>0.0 ms</td>
                  <td>{(comparisonResult.dynamic.mcp_total_time_ms || comparisonResult.dynamic.mcp_time_ms || 0).toFixed(1)} ms</td>
                  <td>Combined MCP overhead (query + transport)</td>
                </tr>
                <tr>
                  <td className="metric-name">Total Experiment Time (ms)</td>
                  <td>{(comparisonResult.baseline.total_experiment_time_ms || comparisonResult.baseline.total_time_ms || 0).toFixed(1)} ms</td>
                  <td>{(comparisonResult.dynamic.total_experiment_time_ms || comparisonResult.dynamic.total_time_ms || 0).toFixed(1)} ms</td>
                  <td>{comparisonResult.time_difference_ms > 0 ? `+${comparisonResult.time_difference_ms.toFixed(1)} ms duration` : `${comparisonResult.time_difference_ms.toFixed(1)} ms duration`}</td>
                </tr>
                <tr className="table-group-header">
                  <td colSpan={4}>Diagnostic & Repair Effectiveness</td>
                </tr>
                <tr>
                  <td className="metric-name">Root Cause Identified</td>
                  <td>
                    {comparisonResult.baseline.root_cause_identified ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Yes</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> No</span>
                    )}
                  </td>
                  <td>
                    {comparisonResult.dynamic.root_cause_identified ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Yes</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> No</span>
                    )}
                  </td>
                  <td>Empirical diagnostic accuracy</td>
                </tr>
                <tr>
                  <td className="metric-name">Fix Generated</td>
                  <td>
                    {comparisonResult.baseline.fix_generated ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Yes</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> No</span>
                    )}
                  </td>
                  <td>
                    {comparisonResult.dynamic.fix_generated ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Yes</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> No</span>
                    )}
                  </td>
                  <td>Candidate patch synthesized</td>
                </tr>
                <tr>
                  <td className="metric-name">Re-execution Passed</td>
                  <td>
                    {comparisonResult.baseline.re_execution_passed ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Passed</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> Failed</span>
                    )}
                  </td>
                  <td>
                    {comparisonResult.dynamic.re_execution_passed ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Passed</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> Failed</span>
                    )}
                  </td>
                  <td>Sandbox exit code 0</td>
                </tr>
                <tr>
                  <td className="metric-name">Fix Correct</td>
                  <td>
                    {comparisonResult.baseline.fix_correct ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Validated</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> Not Validated</span>
                    )}
                  </td>
                  <td>
                    {comparisonResult.dynamic.fix_correct ? (
                      <span className="outcome-pill success"><CheckCircle2 size={12} /> Validated</span>
                    ) : (
                      <span className="outcome-pill failure"><XCircle size={12} /> Not Validated</span>
                    )}
                  </td>
                  <td>Semantic correctness validation</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. Detailed Research Run Inspector (Expandable Modal / Card) */}
      {selectedEvaluationId && (
        <div className="evaluation-inspector-card">
          <div className="inspector-header">
            <div className="inspector-header-left">
              <Layers size={18} className="text-accent" />
              <div>
                <h4>Research Artifact Inspector</h4>
                <div className="inspector-id-row">
                  <span className="font-mono text-xs text-muted">Evaluation ID: {selectedEvaluationId}</span>
                  <button
                    type="button"
                    className="copy-id-btn"
                    onClick={() => handleCopyId(selectedEvaluationId)}
                    title="Copy Evaluation ID to clipboard"
                  >
                    {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
              </div>
            </div>
            <button
              type="button"
              className="close-inspector-btn"
              onClick={() => setSelectedEvaluationId(null)}
              title="Close Inspector"
            >
              <X size={16} />
            </button>
          </div>

          {/* Traceability Location Banner */}
          <div className="inspector-trace-banner">
            <div className="trace-path-info">
              <span className="trace-label">Experiment Artifact Storage:</span>
              <code className="trace-path">backend/data/m8/experiments/{selectedEvaluationId}/</code>
            </div>
            <div className="trace-files-list">
              <span className="trace-file-tag">events.jsonl</span>
              <span className="trace-file-tag">summary.json</span>
              <span className="trace-file-tag">baseline.json</span>
              <span className="trace-file-tag">dynamic.json</span>
            </div>
          </div>

          {/* Inspector Tabs */}
          <div className="inspector-tabs">
            <button
              type="button"
              className={`inspector-tab ${activeInspectTab === 'summary' ? 'active' : ''}`}
              onClick={() => setActiveInspectTab('summary')}
            >
              <Sparkles size={14} />
              <span>Paired Summary</span>
            </button>
            <button
              type="button"
              className={`inspector-tab ${activeInspectTab === 'events' ? 'active' : ''}`}
              onClick={() => setActiveInspectTab('events')}
            >
              <Activity size={14} />
              <span>Lifecycle Events ({inspectionEvents?.length || 0})</span>
            </button>
            <button
              type="button"
              className={`inspector-tab ${activeInspectTab === 'raw' ? 'active' : ''}`}
              onClick={() => setActiveInspectTab('raw')}
            >
              <Terminal size={14} />
              <span>Raw JSON Artifact</span>
            </button>
          </div>

          {isLoadingInspection ? (
            <div className="inspector-loading">
              <RefreshCw size={20} className="spin-icon text-accent" />
              <span>Loading evaluation artifacts & telemetry from backend...</span>
            </div>
          ) : (
            <div className="inspector-content">
              {activeInspectTab === 'summary' && (
                <div className="inspector-summary-view">
                  {inspectionSummary ? (
                    <div className="summary-grid">
                      <div className="summary-mode-card baseline-card">
                        <div className="summary-mode-header">
                          <span className="mode-badge baseline">Baseline Run</span>
                          <span className="font-mono text-xs text-muted">{inspectionSummary.baseline?.experiment_id}</span>
                        </div>
                        <div className="summary-metrics-list">
                          <div className="metric-row">
                            <span>Status:</span>
                            <span className="font-semibold">{inspectionSummary.baseline?.status}</span>
                          </div>
                          <div className="metric-row">
                            <span>Context Size:</span>
                            <span className="font-mono font-bold">{(inspectionSummary.baseline?.context_chars ?? 0).toLocaleString()} chars</span>
                          </div>
                          <div className="metric-row">
                            <span>Total Tokens:</span>
                            <span className="font-mono">
                              {inspectionSummary.baseline?.token_usage_available && inspectionSummary.baseline?.total_tokens !== null
                                ? `${inspectionSummary.baseline.total_tokens.toLocaleString()} tokens`
                                : 'N/A — token usage unavailable'}
                            </span>
                          </div>
                          <div className="metric-row">
                            <span>LLM Calls / MCP:</span>
                            <span>{inspectionSummary.baseline?.llm_calls} call(s) / {inspectionSummary.baseline?.mcp_calls} MCP</span>
                          </div>
                          <div className="metric-row">
                            <span>LLM Time:</span>
                            <span className="font-mono">{(inspectionSummary.baseline?.llm_time_ms ?? 0).toFixed(1)} ms</span>
                          </div>
                          <div className="metric-row">
                            <span>Total Experiment Time:</span>
                            <span className="font-mono">{(inspectionSummary.baseline?.total_experiment_time_ms ?? 0).toFixed(1)} ms</span>
                          </div>
                          <div className="metric-row">
                            <span>Root Cause Identified:</span>
                            <span>{inspectionSummary.baseline?.root_cause_identified ? 'Yes' : 'No'}</span>
                          </div>
                          <div className="metric-row">
                            <span>Fix Correct / Passed:</span>
                            <span>{inspectionSummary.baseline?.fix_correct ? 'Validated' : 'No'}</span>
                          </div>
                        </div>
                      </div>

                      <div className="summary-mode-card dynamic-card">
                        <div className="summary-mode-header">
                          <span className="mode-badge dynamic">Dynamic Run</span>
                          <span className="font-mono text-xs text-muted">{inspectionSummary.dynamic?.experiment_id}</span>
                        </div>
                        <div className="summary-metrics-list">
                          <div className="metric-row">
                            <span>Status:</span>
                            <span className="font-semibold">{inspectionSummary.dynamic?.status}</span>
                          </div>
                          <div className="metric-row">
                            <span>Context Size:</span>
                            <span className="font-mono font-bold text-success">{(inspectionSummary.dynamic?.context_chars ?? 0).toLocaleString()} chars</span>
                          </div>
                          <div className="metric-row">
                            <span>Total Tokens:</span>
                            <span className="font-mono">
                              {inspectionSummary.dynamic?.token_usage_available && inspectionSummary.dynamic?.total_tokens !== null
                                ? `${inspectionSummary.dynamic.total_tokens.toLocaleString()} tokens (Curator: ${inspectionSummary.dynamic.curator_total_tokens ?? 0}, Debugger: ${inspectionSummary.dynamic.debugger_total_tokens ?? 0})`
                                : 'N/A — token usage unavailable'}
                            </span>
                          </div>
                          <div className="metric-row">
                            <span>LLM Calls / MCP:</span>
                            <span>{inspectionSummary.dynamic?.llm_calls} call(s) / {inspectionSummary.dynamic?.mcp_calls} MCP</span>
                          </div>
                          <div className="metric-row">
                            <span>LLM Time:</span>
                            <span className="font-mono">{(inspectionSummary.dynamic?.llm_time_ms ?? 0).toFixed(1)} ms</span>
                          </div>
                          <div className="metric-row">
                            <span>MCP Overhead (total):</span>
                            <span className="font-mono">{(inspectionSummary.dynamic?.mcp_total_time_ms ?? 0).toFixed(1)} ms</span>
                          </div>
                          <div className="metric-row">
                            <span>Total Experiment Time:</span>
                            <span className="font-mono">{(inspectionSummary.dynamic?.total_experiment_time_ms ?? 0).toFixed(1)} ms</span>
                          </div>
                          <div className="metric-row">
                            <span>Root Cause Identified:</span>
                            <span>{inspectionSummary.dynamic?.root_cause_identified ? 'Yes' : 'No'}</span>
                          </div>
                          <div className="metric-row">
                            <span>Fix Correct / Passed:</span>
                            <span>{inspectionSummary.dynamic?.fix_correct ? 'Validated' : 'No'}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="inspector-empty">No paired summary artifact found for this evaluation ID.</div>
                  )}
                </div>
              )}

              {activeInspectTab === 'events' && (
                <div className="inspector-events-view">
                  {inspectionEvents && inspectionEvents.length > 0 ? (
                    <div className="events-timeline">
                      {inspectionEvents.map((evt, idx) => (
                        <div key={`${evt.event}-${idx}`} className="event-timeline-node">
                          <div className="event-timeline-left">
                            <span className="event-step-pill">Step {evt.step ?? idx + 1}</span>
                            <span className="event-time-str">
                              {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '-'}
                            </span>
                          </div>
                          <div className="event-timeline-right">
                            <div className="event-title-line">
                              <span className="event-name-tag">{evt.event}</span>
                              {evt.mode && (
                                <span className={`mode-badge ${evt.mode}`}>{evt.mode}</span>
                              )}
                            </div>
                            <div className="event-details-text">
                              {Object.entries(evt)
                                .filter(([k]) => !['timestamp', 'evaluation_id', 'experiment_id', 'event', 'step', 'mode'].includes(k))
                                .map(([k, v]) => (
                                  <span key={k} className="event-kv-item">
                                    <span className="kv-key">{k}:</span>{' '}
                                    <span className="kv-val">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                                  </span>
                                ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="inspector-empty">No structured events recorded for this evaluation ID.</div>
                  )}
                </div>
              )}

              {activeInspectTab === 'raw' && (
                <div className="inspector-raw-view">
                  <pre className="raw-json-block">
                    {JSON.stringify(inspectionSummary || inspectionEvents, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 6. Experiment History / Dataset Section */}
      <div className="experiments-history-card">
        <div className="history-card-header">
          <div className="flex-row items-center gap-2">
            <Database size={16} className="text-accent" />
            <h4>Evaluation Experiment History</h4>
          </div>
          <span className="text-muted text-xs">Canonical benchmark dataset</span>
        </div>

        {recentExperiments.length === 0 ? (
          <div className="empty-history">
            <Database size={28} className="empty-icon text-dim" />
            <p className="empty-title">No Evaluation Runs Recorded</p>
            <p className="empty-subtitle">Select a benchmark task above and click <strong>"Run Paired Evaluation"</strong> to record experimental metrics.</p>
          </div>
        ) : (
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Evaluation ID</th>
                  <th>Experiment ID</th>
                  <th>Bug</th>
                  <th>Mode</th>
                  <th>Status</th>
                  <th>Context Size (chars)</th>
                  <th>Reduct %</th>
                  <th>Total Tokens</th>
                  <th>MCP Calls</th>
                  <th>Total Time (ms)</th>
                  <th>Fix Correct</th>
                  <th>Timestamp</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {recentExperiments.map((exp) => (
                  <tr key={exp.experiment_id}>
                    <td className="font-mono text-xs" title={exp.evaluation_id}>
                      {exp.evaluation_id ? exp.evaluation_id.slice(0, 16) + '...' : '-'}
                    </td>
                    <td className="font-mono text-xs" title={exp.experiment_id}>
                      {exp.experiment_id ? exp.experiment_id.slice(-14) : '-'}
                    </td>
                    <td className="font-bold">{exp.bug_id}</td>
                    <td>
                      <span className={`mode-badge ${exp.mode}`}>
                        {exp.mode === 'baseline' ? 'Baseline' : 'Dynamic'}
                      </span>
                    </td>
                    <td>
                      <span className={`status-tag ${exp.status === 'completed' ? 'completed' : 'invalid'}`}>
                        {exp.status === 'completed' ? 'Completed' : exp.status}
                      </span>
                    </td>
                    <td>{(exp.context_chars ?? exp.context_size ?? 0).toLocaleString()} chars</td>
                    <td>
                      {exp.context_reduction_percent !== null && exp.context_reduction_percent > 0
                        ? `-${exp.context_reduction_percent}%`
                        : '-'}
                    </td>
                    <td>
                      {exp.token_usage_available && exp.total_tokens !== null
                        ? exp.total_tokens.toLocaleString()
                        : 'N/A'}
                    </td>
                    <td>{exp.mcp_calls}</td>
                    <td>{(exp.total_experiment_time_ms || exp.total_time_ms || 0).toFixed(0)} ms</td>
                    <td>
                      {exp.fix_correct ? (
                        <span className="text-success text-xs font-semibold">Validated</span>
                      ) : (
                        <span className="text-muted text-xs">No</span>
                      )}
                    </td>
                    <td className="text-xs text-muted">
                      {exp.timestamp ? new Date(exp.timestamp).toLocaleTimeString() : '-'}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="table-inspect-btn"
                        onClick={() => handleInspectEvaluation(exp.evaluation_id)}
                        title="Inspect run artifacts and telemetry"
                      >
                        <Eye size={12} />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
