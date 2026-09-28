import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 3 minutes to accommodate multi-step LLM curation & validation
});

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
    if (error.code === 'ECONNABORTED') {
      throw new Error('Diagnosis timed out. The AI model is taking longer than expected.');
    } else if (error.response && error.response.data && error.response.data.detail) {
      throw new Error(error.response.data.detail);
    } else if (error.response && error.response.status === 500) {
      throw new Error('Diagnosis service encountered an error. Please try again.');
    } else {
      throw new Error(error.message || 'Unable to generate diagnosis. Please try again.');
    }
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
    if (error.code === 'ECONNABORTED') {
      throw new Error('Fix generation timed out. The AI model is taking longer than expected.');
    } else if (error.response && error.response.data && error.response.data.detail) {
      throw new Error(error.response.data.detail);
    } else if (error.response && error.response.status === 500) {
      throw new Error('Bug fixing service encountered an error. Please try again.');
    } else {
      throw new Error(error.message || 'Unable to generate fix. Please try again.');
    }
  }
}
