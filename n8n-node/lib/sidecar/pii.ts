/**
 * PII detection for the Trusera Sidecar.
 *
 * Regex-based scanning for personally identifiable information.
 * Designed for high precision (few false positives) over recall.
 */

import { API_KEY_PATTERNS } from '../config';

/** Maximum text length to scan (100 KB) to prevent ReDoS / perf issues. */
const MAX_SCAN_LENGTH = 100_000;

/** A single PII match. */
export interface PiiMatch {
  type: string;
  value: string;
  redacted: string;
  position: number;
}

interface PiiPattern {
  type: string;
  pattern: RegExp;
  /** Optional post-match validator (e.g. Luhn check for credit cards). */
  validate?: (match: string) => boolean;
}

/** Luhn algorithm for credit card validation. */
function luhnCheck(num: string): boolean {
  const digits = num.replace(/[\s-]/g, '');
  if (!/^\d{13,19}$/.test(digits)) return false;

  let sum = 0;
  let alternate = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let n = parseInt(digits[i], 10);
    if (alternate) {
      n *= 2;
      if (n > 9) n -= 9;
    }
    sum += n;
    alternate = !alternate;
  }
  return sum % 10 === 0;
}

const PII_PATTERNS: readonly PiiPattern[] = [
  {
    type: 'ssn',
    pattern: /\b\d{3}-\d{2}-\d{4}\b/g,
  },
  {
    type: 'credit_card',
    pattern: /\b(?:\d[ -]*?){13,19}\b/g,
    validate: luhnCheck,
  },
  {
    type: 'email',
    pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
  },
  {
    type: 'phone_us',
    pattern: /\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g,
  },
  {
    type: 'ip_address',
    pattern: /\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b/g,
  },
];

function redactValue(type: string, value: string): string {
  return `[REDACTED_${type.toUpperCase()}]`;
}

/**
 * Detect PII in a text string.
 * Returns all matches found. Scans up to MAX_SCAN_LENGTH bytes.
 */
export function detectPii(text: string): PiiMatch[] {
  if (!text) return [];

  const scanText = text.length > MAX_SCAN_LENGTH ? text.slice(0, MAX_SCAN_LENGTH) : text;
  const matches: PiiMatch[] = [];

  // Built-in PII patterns
  for (const { type, pattern, validate } of PII_PATTERNS) {
    // Reset lastIndex for global regex
    pattern.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(scanText)) !== null) {
      const value = match[0];
      if (validate && !validate(value)) continue;
      matches.push({
        type,
        value,
        redacted: redactValue(type, value),
        position: match.index,
      });
    }
  }

  // API key patterns (reused from config.ts)
  for (const { pattern, provider } of API_KEY_PATTERNS) {
    const globalPattern = new RegExp(pattern.source, 'gi');
    let match: RegExpExecArray | null;
    while ((match = globalPattern.exec(scanText)) !== null) {
      matches.push({
        type: 'api_key',
        value: match[0],
        redacted: `[REDACTED_API_KEY_${provider.toUpperCase()}]`,
        position: match.index,
      });
    }
  }

  return matches;
}

/**
 * Redact all PII matches in a text string.
 * Replaces each match with [REDACTED_<TYPE>].
 */
export function redactPii(text: string, matches: PiiMatch[]): string {
  if (!matches.length) return text;

  // Sort by position descending so replacements don't shift indices
  const sorted = [...matches].sort((a, b) => b.position - a.position);
  let result = text;
  for (const m of sorted) {
    result = result.slice(0, m.position) + m.redacted + result.slice(m.position + m.value.length);
  }
  return result;
}

/** Quick boolean check: does the text contain any PII? */
export function containsPii(text: string): boolean {
  return detectPii(text).length > 0;
}
