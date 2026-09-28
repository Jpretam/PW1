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
  HelpCircle,
  TrendingDown,
  RefreshCw,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import {
  getBenchmarks,
  runPairedEvaluation,
  getRecentExperiments,
} from '../services/evaluationService';

export const EvaluationSection = ({ onLoadBenchmarkCode }) => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [selectedBugId, setSelectedBugId] = useState('B001');
  const [isRunning, setIsRunning] = useState(false);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [evalError, setEvalError] = useState(null);
  const [recentExperiments, setRecentExperiments] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

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
      const data = await getRecentExperiments(15);
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
    } catch (err) {
      setEvalError(err.response?.data?.detail || err.message || 'Evaluation failed to complete.');
    } finally {
      setIsRunning(false);
    }
  };

  const selectedBench = benchmarks.find((b) => b.bug_id === selectedBugId);

  return (
    <div className="evaluation-container">
      <div className="evaluation-header">
        <div className="evaluation-header-left">
          <FlaskConical size={20} className="text-accent" />
          <div>
            <h3 className="evaluation-title">M8: Baseline Comparison & Empirical Evaluation</h3>
            <p className="evaluation-subtitle">
              Evaluating <strong>Baseline (Full Context)</strong> vs <strong>Dynamic (Curated Context via MCP)</strong> on controlled benchmarks
            </p>
          </div>
        </div>
        <button
          type="button"
          className="history-refresh-btn"
          onClick={fetchHistory}
          title="Refresh experiment records"
        >
          <RefreshCw size={14} className={isLoadingHistory ? 'spin-icon' : ''} />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* Benchmark Task Selection Toolbar */}
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

      {/* Section 11: Side-by-Side Comparison View */}
      {comparisonResult && (
        <div className="comparison-card">
          <div className="comparison-card-header">
            <h4>Experimental Comparison — Benchmark {comparisonResult.bug_id}</h4>
            <div className="reduction-pill">
              <TrendingDown size={14} />
              <span>Context Reduction: {comparisonResult.context_reduction_percent}%</span>
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
                <tr>
                  <td className="metric-name">Context Size</td>
                  <td>{comparisonResult.baseline.context_size.toLocaleString()} chars</td>
                  <td>{comparisonResult.dynamic.context_size.toLocaleString()} chars</td>
                  <td className="text-reduction">
                    -{comparisonResult.context_reduction_percent}% reduction
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">Total Tokens</td>
                  <td>
                    {comparisonResult.baseline.total_tokens > 0
                      ? comparisonResult.baseline.total_tokens.toLocaleString()
                      : '0 (recorded)'}
                  </td>
                  <td>
                    {comparisonResult.dynamic.total_tokens > 0
                      ? `${comparisonResult.dynamic.total_tokens.toLocaleString()} (Curator: ${comparisonResult.dynamic.curator_total_tokens}, Debugger: ${comparisonResult.dynamic.debugger_total_tokens})`
                      : '0 (recorded)'}
                  </td>
                  <td>
                    {comparisonResult.token_reduction_percent !== 0
                      ? `${comparisonResult.token_reduction_percent}% token delta`
                      : 'Real metadata tracked'}
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">LLM Calls</td>
                  <td>{comparisonResult.baseline.llm_calls}</td>
                  <td>{comparisonResult.dynamic.llm_calls}</td>
                  <td>
                    {comparisonResult.dynamic.llm_calls > comparisonResult.baseline.llm_calls
                      ? `+${comparisonResult.dynamic.llm_calls - comparisonResult.baseline.llm_calls} (Curator step)`
                      : 'Identical'}
                  </td>
                </tr>
                <tr>
                  <td className="metric-name">MCP Tool Calls</td>
                  <td>0 (Direct Context)</td>
                  <td>{comparisonResult.dynamic.mcp_calls} (Selective Retrieval)</td>
                  <td>Dynamic query via MCP</td>
                </tr>
                <tr>
                  <td className="metric-name">LLM Time</td>
                  <td>{comparisonResult.baseline.llm_time_ms.toFixed(1)} ms</td>
                  <td>{comparisonResult.dynamic.llm_time_ms.toFixed(1)} ms</td>
                  <td>Total model query duration</td>
                </tr>
                <tr>
                  <td className="metric-name">MCP Time</td>
                  <td>0 ms</td>
                  <td>
                    {comparisonResult.dynamic.mcp_time_ms.toFixed(1)} ms
                    <span className="sub-metric">
                      (Query: {comparisonResult.dynamic.mcp_query_time_ms.toFixed(1)}ms, Transport: {comparisonResult.dynamic.mcp_transport_time_ms.toFixed(1)}ms)
                    </span>
                  </td>
                  <td>Isolated tool execution</td>
                </tr>
                <tr>
                  <td className="metric-name">Total Experiment Time</td>
                  <td>{comparisonResult.baseline.total_time_ms.toFixed(1)} ms</td>
                  <td>{comparisonResult.dynamic.total_time_ms.toFixed(1)} ms</td>
                  <td>{comparisonResult.time_difference_ms > 0 ? `+${comparisonResult.time_difference_ms} ms` : `${comparisonResult.time_difference_ms} ms`}</td>
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
                  <td>Empirical accuracy</td>
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
                  <td>Candidate patch</td>
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
                  <td>Sandbox verification</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Dataset / Experiment History Section */}
      <div className="experiments-history-card">
        <div className="history-card-header">
          <div className="flex-row items-center gap-2">
            <Database size={16} className="text-accent" />
            <h4>Logged Experiment Records (m8_experiments.csv)</h4>
          </div>
          <span className="text-muted text-xs">Dataset persisted on backend</span>
        </div>

        {recentExperiments.length === 0 ? (
          <div className="empty-history">
            No evaluation runs logged yet. Run a paired evaluation or run debugging to generate records.
          </div>
        ) : (
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Experiment ID</th>
                  <th>Bug</th>
                  <th>Mode</th>
                  <th>Context Size</th>
                  <th>Reduct %</th>
                  <th>Total Tokens</th>
                  <th>MCP Calls</th>
                  <th>Total Time</th>
                  <th>Fix Passed</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {recentExperiments.map((exp) => (
                  <tr key={exp.experiment_id}>
                    <td className="font-mono text-xs">{exp.experiment_id.slice(0, 22)}...</td>
                    <td className="font-bold">{exp.bug_id}</td>
                    <td>
                      <span className={`mode-badge ${exp.mode}`}>
                        {exp.mode === 'baseline' ? 'Baseline' : 'Dynamic'}
                      </span>
                    </td>
                    <td>{exp.context_size.toLocaleString()} chars</td>
                    <td>{exp.context_reduction_percent > 0 ? `-${exp.context_reduction_percent}%` : '-'}</td>
                    <td>{exp.total_tokens.toLocaleString()}</td>
                    <td>{exp.mcp_calls}</td>
                    <td>{exp.total_time_ms.toFixed(0)} ms</td>
                    <td>
                      {exp.fix_correct ? (
                        <span className="text-success text-xs font-semibold">Passed</span>
                      ) : (
                        <span className="text-danger text-xs font-semibold">Failed</span>
                      )}
                    </td>
                    <td className="text-xs text-muted">
                      {exp.timestamp ? new Date(exp.timestamp).toLocaleTimeString() : '-'}
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
