import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000, // 15 seconds network timeout
});

export const executeCode = async (language, code, stdin = '') => {
  try {
    const response = await apiClient.post('/execute', {
      language,
      code,
      stdin,
    });
    return response.data;
  } catch (error) {
    if (error.code === 'ECONNABORTED') {
      return {
        status: 'timeout',
        language,
        stdout: '',
        stderr: 'Request timed out. Please try again.',
        exit_code: null,
        execution_time: 15.0,
      };
    } else {
      return {
        status: 'execution_error',
        language,
        stdout: '',
        stderr: 'Something went wrong. Please try again.',
        exit_code: 1,
        execution_time: 0,
      };
    }
  }
};
