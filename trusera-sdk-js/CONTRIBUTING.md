# Contributing to Trusera SDK

Thank you for your interest in contributing to the Trusera SDK for JavaScript/TypeScript!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/Trusera/trusera-sdk-js.git
cd trusera-sdk-js
```

2. Install dependencies:
```bash
npm install
```

3. Build the project:
```bash
npm run build
```

4. Run tests:
```bash
npm test
```

## Project Structure

```
trusera-sdk-js/
├── src/
│   ├── index.ts           # Main exports
│   ├── client.ts          # TruseraClient implementation
│   ├── interceptor.ts     # HTTP interceptor
│   ├── events.ts          # Event types and utilities
│   └── integrations/
│       └── langchain.ts   # LangChain.js integration
├── tests/                 # Vitest test files
├── dist/                  # Build output (gitignored)
└── package.json
```

## Code Style

- Use TypeScript strict mode
- Follow existing code formatting (we use ESLint)
- Add JSDoc comments for public APIs
- Use modern ES2022+ features (native fetch, crypto.randomUUID)
- Prefer type inference over explicit annotations when clear

## Testing

- Write tests for all new features
- Maintain or improve code coverage
- Use Vitest for all tests
- Mock external dependencies (fetch, etc.)

Run tests with:
```bash
npm test
npm run test:watch  # Watch mode
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`npm test && npm run lint`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Commit Message Guidelines

Use clear, descriptive commit messages:

- `feat: add support for custom event metadata`
- `fix: resolve race condition in flush timer`
- `docs: update LangChain integration examples`
- `test: add coverage for interceptor exclude patterns`
- `refactor: simplify event enrichment logic`

## Release Process

Releases are automated via GitHub Actions:

1. Update version in `package.json`
2. Create a git tag: `git tag v0.1.1`
3. Push tag: `git push origin v0.1.1`
4. GitHub Actions will build, test, and publish to npm

## Questions?

Open an issue or reach out to support@trusera.io

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
