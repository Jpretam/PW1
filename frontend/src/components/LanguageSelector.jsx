import React from 'react';
import { Code2 } from 'lucide-react';

export const LanguageSelector = ({ language, onLanguageChange, disabled }) => {
  return (
    <div className="language-selector-wrapper">
      <Code2 size={16} className="control-icon text-muted" />
      <label htmlFor="language-select" className="control-label">
        Language
      </label>
      <select
        id="language-select"
        value={language}
        onChange={(e) => onLanguageChange(e.target.value)}
        disabled={disabled}
        className="language-select"
      >
        <option value="python">Python 3</option>
        <option value="java">Java 17</option>
      </select>
    </div>
  );
};

