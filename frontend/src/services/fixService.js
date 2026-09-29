import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 3 minutes to accommodate multi-step LLM curation & validation
});

import { getFriendlyErrorMessage, AI_UNAVAILABLE_MESSAGE } from '../utils/errorUtils';

export async function diagnoseExecution(executionId, mode = 'dynamic') {
  if (!executionId) {
    throw new Error('Execution ID is required for diagnosis.');
  }

  try {
    const response = await apiClient.post('/debug/diagnose', {
      execution_id: executionId,
      mode,
    });
    return response.data;
  } catch (error) {
    throw new Error(getFriendlyErrorMessage(error, AI_UNAVAILABLE_MESSAGE));
  }
}

export async function fixExecution(executionId, maxAttempts = 3, mode = 'dynamic') {
  if (!executionId) {
    throw new Error('Execution ID is required for automatic fixing.');
  }

  try {
    const response = await apiClient.post('/debug/fix', {
      execution_id: executionId,
      max_attempts: maxAttempts,
      mode,
    });
    return response.data;
  } catch (error) {
    throw new Error(getFriendlyErrorMessage(error, AI_UNAVAILABLE_MESSAGE));
  }
}
