import { detectPii, redactPii, containsPii } from '../../lib/sidecar/pii';

describe('PII Detection', () => {
  describe('detectPii', () => {
    it('should return empty array for empty input', () => {
      expect(detectPii('')).toEqual([]);
      expect(detectPii(null as unknown as string)).toEqual([]);
    });

    it('should detect SSN', () => {
      const matches = detectPii('My SSN is 123-45-6789');
      expect(matches).toHaveLength(1);
      expect(matches[0].type).toBe('ssn');
      expect(matches[0].value).toBe('123-45-6789');
    });

    it('should detect email addresses', () => {
      const matches = detectPii('Contact me at user@example.com please');
      expect(matches).toHaveLength(1);
      expect(matches[0].type).toBe('email');
      expect(matches[0].value).toBe('user@example.com');
    });

    it('should detect credit card numbers (Luhn valid)', () => {
      // 4111 1111 1111 1111 is a valid Luhn test number
      const matches = detectPii('Card: 4111111111111111');
      const ccMatches = matches.filter((m) => m.type === 'credit_card');
      expect(ccMatches.length).toBeGreaterThanOrEqual(1);
    });

    it('should reject invalid credit card numbers (Luhn fails)', () => {
      const matches = detectPii('Number: 1234567890123456');
      const ccMatches = matches.filter((m) => m.type === 'credit_card');
      expect(ccMatches).toHaveLength(0);
    });

    it('should detect US phone numbers', () => {
      const matches = detectPii('Call me at (555) 123-4567');
      const phoneMatches = matches.filter((m) => m.type === 'phone_us');
      expect(phoneMatches.length).toBeGreaterThanOrEqual(1);
    });

    it('should detect IP addresses', () => {
      const matches = detectPii('Server is at 192.168.1.100');
      const ipMatches = matches.filter((m) => m.type === 'ip_address');
      expect(ipMatches).toHaveLength(1);
      expect(ipMatches[0].value).toBe('192.168.1.100');
    });

    it('should detect API keys', () => {
      const matches = detectPii('key: sk-proj-abc123def456ghi789jkl012');
      const apiKeyMatches = matches.filter((m) => m.type === 'api_key');
      expect(apiKeyMatches.length).toBeGreaterThanOrEqual(1);
    });

    it('should detect multiple PII types in one text', () => {
      const text = 'SSN: 123-45-6789, email: test@test.com, IP: 10.0.0.1';
      const matches = detectPii(text);
      const types = new Set(matches.map((m) => m.type));
      expect(types.has('ssn')).toBe(true);
      expect(types.has('email')).toBe(true);
      expect(types.has('ip_address')).toBe(true);
    });

    it('should not match benign text', () => {
      const matches = detectPii('Hello, this is a regular message with no PII.');
      expect(matches).toHaveLength(0);
    });
  });

  describe('redactPii', () => {
    it('should redact matched PII', () => {
      const text = 'SSN is 123-45-6789 and email is a@b.com';
      const matches = detectPii(text);
      const redacted = redactPii(text, matches);
      expect(redacted).toContain('[REDACTED_SSN]');
      expect(redacted).toContain('[REDACTED_EMAIL]');
      expect(redacted).not.toContain('123-45-6789');
      expect(redacted).not.toContain('a@b.com');
    });

    it('should return original text when no matches', () => {
      const text = 'Nothing here';
      expect(redactPii(text, [])).toBe(text);
    });
  });

  describe('containsPii', () => {
    it('should return true when PII is present', () => {
      expect(containsPii('SSN: 123-45-6789')).toBe(true);
    });

    it('should return false when no PII', () => {
      expect(containsPii('Just a regular string')).toBe(false);
    });
  });
});
