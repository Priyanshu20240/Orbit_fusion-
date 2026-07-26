// src/test/setup.js
//
// Vitest global setup:
//  - jest-dom matchers (already in place).
//  - MSW server lifecycle so every test runs against the same handlers
//    from ./handlers.js.

import '@testing-library/jest-dom';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { setupServer } from 'msw/node';
import { handlers } from './handlers.js';

export const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
