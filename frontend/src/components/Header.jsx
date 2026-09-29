import React from 'react';
import { Terminal, ShieldCheck } from 'lucide-react';

export const Header = () => {
  return (
    <header className="app-header">
      <div className="header-content">
        <div className="title-group">
          <div className="icon-wrapper">
            <Terminal className="header-icon" size={20} />
          </div>
          <div>
            <div className="header-title-row">
              <h1 className="header-title">PW1</h1>
              <span className="header-tag">Research Platform</span>
            </div>
            <p className="header-subtitle">Dynamic Context Curation & Runtime Debugging Environment</p>
          </div>
        </div>
        <div className="header-status-badge">
          <ShieldCheck size={14} className="text-success" />
          <span>Secure Execution Sandbox</span>
        </div>
      </div>
    </header>
  );
};

