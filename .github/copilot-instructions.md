# GitHub Copilot / Workspace Instructions for mavrov.de

You are completing code for `mavrov.de`, acting as an elite software engineer. This project leverages Gemini, Claude, and other advanced cloud models; your output must match top-tier architectural logic perfectly.

## Standard Directives

1. **Zero-Defect Goal:**
   - Both the frontend and backend require 100% test coverage. Do not write feature code without accompanying tests (`pytest` for backend, `vitest` for frontend).

2. **Backend Framework (Python 3.12 / FastAPI):**
   - Strictly follow `ruff` rules. Format your output to mirror `ruff check` and `ruff format` specifications. Single violations will crash the CI build.
   - Employ `async`/`await` for all non-locking I/O operations, particularly interactions with `asyncpg` within SQLALchemy bindings.
   - Utilize standard type hints across all functions checked rigorously by `mypy`.

3. **Frontend Framework (Angular 18):**
   - Default to using Angular Signals for local state management (e.g., `signal()`, `computed()`).
   - Accommodate SSR constraints. Ensure that code referencing the DOM elements or `window` objects first checks against the Angular `isPlatformBrowser` utility.

4. **Testing Context:**
   - E2E scripts are governed by Playwright. Because UI changes trigger quickly on CSR but might take a moment to initialize after Angular routes, implement micro-waits (`waitForTimeout`) prior to fast `fill` behaviors.
   
Take a step-by-step approach when generating code. Provide robust, production-grade solutions.
