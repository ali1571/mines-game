Django HTMX Mines Game

A real-time, server-rendered 3x3 Mines strategy game built with Django, HTMX, and Tailwind CSS. The application features dynamic UI updates without full page reloads, atomic token ledger transactions, stateful session management, and integrated user verification workflows.
🚀 Features

    Interactive 3x3 Mines Grid: Fast, reactive gameplay powered by HTMX Out-of-Bounds (hx-swap-oob) updates.

    Atomic Balance Ledger: Database-level locking (select_for_update()) on in-game token balances to prevent race conditions during round starts and reward claims.

    Dynamic Rewards & Multipliers: Scaled reward multipliers calculated based on consecutive safe tile reveals.

    Session-Based Game State: Preserves ongoing game state across reloads and tracks active round allocations.

    User Authentication & Verification: Multi-step modal login/signup flow, rate-limited auth, and account verification pipeline.

    Wallet & Receipt Tracking: Token top-up receipt upload mechanism and withdrawal request handling.

    Audit Logging: Logs IP addresses, device types, user agents, and round outcomes to GameLog.

🛠️ Tech Stack

    Backend: Python 3.10+, Django 4.2+

    Frontend: HTMX, Tailwind CSS

    Database: PostgreSQL / SQLite

    Security & Utilities: django-ratelimit, python-magic, Pillow

📂 Key Architecture Overview

    home: Renders the main board and restores ongoing game states from session data.

    start_game: Deducts the token entry amount using atomic locks, initializes mine locations, and creates a GameLog.

    reveal_tile: Handles tile clicks, checks for mines, updates reward multipliers, or triggers round-over states.

    cashout: Calculates final reward claims, credits user token balance atomically, and closes the active game state.

    submit_kyc: Validates account verification document uploads (MIME type, file size, image verification) and updates user status.
