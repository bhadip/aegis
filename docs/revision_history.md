## v0.14.1 (2026-11-25)

### New Features
- **Multi-Profile News Intelligence**: Independent ND100 and XAUUSD scan profiles with separate keywords, RSS feeds, and schedules
- **Profile-Specific Scheduling**: Busy/quiet hours configuration per profile (30min during busy, 3h during quiet)
- **Economic Events Calendar**: Real-time ForexFactory integration with PAST/NEXT event display
- **Event Alerts**: Telegram notifications A minutes before events and at release time
- **Stale Scan Detection**: Dashboard banner and Telegram alerts when scan results haven't changed
- **Account Number Display**: Live account number from MT5 shown on dashboard
- **Custom Sources**: Admin can add custom keywords and RSS feeds per profile

### Bug Fixes
- Fixed HTML artifacts in main.py causing syntax errors
- Fixed JavaScript corruption in app.js (copy-paste artifacts)
- Fixed Economic Events PAST display using rolling 10-day event store
- Fixed profile switching to properly load profile-specific configuration
- Fixed Telegram message tagging to show profile name (ND100/XAUUSD)

### Known Issues
- Economic Events PAST may not show early in the week if no high-impact USD events have occurred yet (rolling store populates after first event)
- Logo/favicon display requires manual file placement in web-ui/ directory

---

# AEGIS Revision History

