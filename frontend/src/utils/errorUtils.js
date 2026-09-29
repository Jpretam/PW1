/**
 * Utility functions for user-friendly error formatting.
 * Sanitizes technical, provider, and container details into safe messages.
 */

export const AI_UNAVAILABLE_MESSAGE = 'AI service is currently unavailable. Please try again later.';
export const GENERIC_ERROR_MESSAGE = 'Something went wrong. Please try again.';

export function getFriendlyErrorMessage(error, defaultFallback = GENERIC_ERROR_MESSAGE) {
  if (!error) return defaultFallback;

  // Extract raw error message
  const rawMsg =
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    (typeof error === 'string' ? error : '');

  const lower = String(rawMsg).toLowerCase();

  // Check if it is an AI, LLM, or provider failure
  if (
    lower.includes('ai service') ||
    lower.includes('llm') ||
    lower.includes('openrouter') ||
    lower.includes('openai') ||
    lower.includes('model') ||
    lower.includes('rate limit') ||
    lower.includes('quota') ||
    lower.includes('token') ||
    lower.includes('balance') ||
    lower.includes('api key') ||
    lower.includes('provider') ||
    lower.includes('timeout') ||
    lower.includes('curat') ||
    lower.includes('debugger') ||
    lower.includes('fixer')
  ) {
    return AI_UNAVAILABLE_MESSAGE;
  }

  // Check if it is an internal deployment/technical detail leak
  if (
    lower.includes('docker') ||
    lower.includes('container') ||
    lower.includes('fastapi') ||
    lower.includes('traceback') ||
    lower.includes('exception') ||
    lower.includes('stack') ||
    lower.includes('internal server') ||
    lower.includes('status code 500') ||
    lower.includes('500') ||
    lower.includes('localhost') ||
    lower.includes('econnrefused') ||
    lower.includes('network error')
  ) {
    return defaultFallback;
  }

  // If already our standard friendly message, keep it
  if (rawMsg === AI_UNAVAILABLE_MESSAGE || rawMsg === GENERIC_ERROR_MESSAGE) {
    return rawMsg;
  }

  // For other unexpected errors, return the fallback
  return defaultFallback;
}

export function sanitizeErrorDetail(err) {
  if (!err) return null;
  if (typeof err === 'object') {
    if (err.status === 'llm_error') {
      return AI_UNAVAILABLE_MESSAGE;
    }
    const candidate = err.detail || err.message || err.stderr || '';
    if (typeof candidate === 'string') {
      return getFriendlyErrorMessage(candidate);
    }
  }
  return getFriendlyErrorMessage(err);
}
