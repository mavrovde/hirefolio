import 'zone.js';
import 'zone.js/testing';
import { vi, afterEach } from 'vitest';
import '@analogjs/vite-plugin-angular/setup-vitest';
import { getTestBed, TestBed } from '@angular/core/testing';
import {
  BrowserDynamicTestingModule,
  platformBrowserDynamicTesting,
} from '@angular/platform-browser-dynamic/testing';

// Initialize the Angular testing environment only once.
const testBed = getTestBed();
if (!testBed.platform) {
  testBed.initTestEnvironment(
    BrowserDynamicTestingModule,
    platformBrowserDynamicTesting(),
    {
      teardown: { destroyAfterEach: true },
    }
  );
}

// Ensure the test module is reset after each test to prevent instantiation errors.
afterEach(() => {
  TestBed.resetTestingModule();
});

// Global mocks
const mockLocalStorage = {
  store: {} as Record<string, string>,
  getItem: vi.fn((key: string) => {
    return key in mockLocalStorage.store ? mockLocalStorage.store[key] : null;
  }),
  setItem: vi.fn((key: string, value: string) => {
    mockLocalStorage.store[key] = `${value}`;
  }),
  removeItem: vi.fn((key: string) => {
    delete mockLocalStorage.store[key];
  }),
  clear: vi.fn(() => {
    mockLocalStorage.store = {};
  }),
  key: vi.fn((index: number) => {
    return Object.keys(mockLocalStorage.store)[index] || null;
  }),
  get length() {
    return Object.keys(this.store).length;
  }
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});
