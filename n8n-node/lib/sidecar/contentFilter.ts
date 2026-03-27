/**
 * Content filtering for the Trusera Sidecar.
 *
 * Pattern-based detection for prompt injection and dangerous content.
 * Conservative patterns — high precision, lower recall. The platform's
 * Cedar policies handle nuanced enforcement; these are a lightweight first pass.
 */

/** Maximum text length to scan (100 KB). */
const MAX_SCAN_LENGTH = 100_000;

/** A single content filter match. */
export interface ContentFilterResult {
  type: 'prompt_injection' | 'dangerous_content';
  name: string;
  matched: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
}

interface FilterPattern {
  name: string;
  pattern: RegExp;
  severity: ContentFilterResult['severity'];
  type: ContentFilterResult['type'];
}

const PROMPT_INJECTION_PATTERNS: readonly FilterPattern[] = [
  {
    name: 'ignore_instructions',
    pattern: /ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts|context|rules)/gi,
    severity: 'critical',
    type: 'prompt_injection',
  },
  {
    name: 'role_reassignment',
    pattern: /you\s+are\s+now\s+(?:a|an|the|my)\s+/gi,
    severity: 'high',
    type: 'prompt_injection',
  },
  {
    name: 'system_prompt_extraction',
    pattern: /(?:repeat|show|reveal|print|output|display|tell\s+me)\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions|rules|guidelines)/gi,
    severity: 'high',
    type: 'prompt_injection',
  },
  {
    name: 'jailbreak_dan',
    pattern: /\bDAN\b.*?(?:do\s+anything\s+now|jailbreak|bypass|unrestricted)/gi,
    severity: 'critical',
    type: 'prompt_injection',
  },
  {
    name: 'delimiter_injection',
    pattern: /(?:<\/?system>|<\/?user>|<\/?assistant>|\[INST\]|\[\/INST\]|<<SYS>>|<\/SYS>>)/gi,
    severity: 'high',
    type: 'prompt_injection',
  },
  {
    name: 'instruction_override',
    pattern: /(?:new\s+instructions?|override\s+(?:instructions?|rules)|forget\s+(?:everything|all|previous))/gi,
    severity: 'critical',
    type: 'prompt_injection',
  },
  {
    name: 'base64_instruction',
    pattern: /(?:decode|execute|run|eval)\s+(?:this\s+)?(?:base64|b64)\s*[:=]/gi,
    severity: 'high',
    type: 'prompt_injection',
  },
];

const DANGEROUS_CONTENT_PATTERNS: readonly FilterPattern[] = [
  {
    name: 'sql_injection_in_llm',
    pattern: /(?:;\s*DROP\s+TABLE|;\s*DELETE\s+FROM|UNION\s+(?:ALL\s+)?SELECT|'\s*OR\s+'1'\s*=\s*'1)/gi,
    severity: 'high',
    type: 'dangerous_content',
  },
  {
    name: 'path_traversal',
    pattern: /(?:\.\.\/){2,}|(?:\.\.\\){2,}/g,
    severity: 'medium',
    type: 'dangerous_content',
  },
  {
    name: 'shell_injection',
    pattern: /(?:;\s*(?:rm|wget|curl|nc|bash|sh|python|perl|ruby)\s+-|`[^`]*`|\$\([^)]*\))/gi,
    severity: 'high',
    type: 'dangerous_content',
  },
  {
    name: 'encoded_payload',
    pattern: /(?:&#x[0-9a-f]{2,4};){3,}|(?:%[0-9a-f]{2}){5,}/gi,
    severity: 'medium',
    type: 'dangerous_content',
  },
];

function runPatterns(text: string, patterns: readonly FilterPattern[]): ContentFilterResult[] {
  const results: ContentFilterResult[] = [];
  for (const { name, pattern, severity, type } of patterns) {
    pattern.lastIndex = 0;
    const match = pattern.exec(text);
    if (match) {
      results.push({ type, name, matched: match[0], severity });
    }
  }
  return results;
}

/** Detect prompt injection patterns. */
export function detectPromptInjection(text: string): ContentFilterResult[] {
  if (!text) return [];
  const scanText = text.length > MAX_SCAN_LENGTH ? text.slice(0, MAX_SCAN_LENGTH) : text;
  return runPatterns(scanText, PROMPT_INJECTION_PATTERNS);
}

/** Detect dangerous content patterns. */
export function detectDangerousContent(text: string): ContentFilterResult[] {
  if (!text) return [];
  const scanText = text.length > MAX_SCAN_LENGTH ? text.slice(0, MAX_SCAN_LENGTH) : text;
  return runPatterns(scanText, DANGEROUS_CONTENT_PATTERNS);
}

/** Combined content filter — runs both injection + dangerous content checks. */
export function runContentFilter(text: string): ContentFilterResult[] {
  if (!text) return [];
  const scanText = text.length > MAX_SCAN_LENGTH ? text.slice(0, MAX_SCAN_LENGTH) : text;
  return [
    ...runPatterns(scanText, PROMPT_INJECTION_PATTERNS),
    ...runPatterns(scanText, DANGEROUS_CONTENT_PATTERNS),
  ];
}
