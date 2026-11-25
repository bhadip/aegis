## v0.14.7 (2026-11-25)
- **Multi-Profile Support**: Added ND100 and XAUUSD scan profiles with independent schedules.
- **UI Updates**: 
  - Version number now syncs with code version (SOP).
  - Added favicon/icon to browser tab.
  - Restructured News Intelligence tab into "Economic Events" and "News Scan" cards.
- **Backend**: 
  - Wired `news_engine` for profile management and event fetching.
  - Added account number display on Dashboard.

# AEGIS Changelog

## v0.14.2 (2026-11-25)
- **News Intelligence UI Restructure**: Split into two distinct cards: "Economic Events" and "News Scan".
- **Economic Events Card**: Shows NEXT and PAST events with Actual/Forecast/Previous details. Added Telegram alert A and Dashboard past window B inputs.
- **News Scan Card**: Profile selector, schedule dropdown, and Run Scan button in one row. Keywords and RSS Feeds sections with Active/Inactive/Custom groupings.
- **Past Events Fix**: Implemented rolling 7-day event cache to ensure PAST events are always displayed.
- **Logo & Icon**: Fixed static file paths and ensured assets are copied to container.

## v0.14.1 (2026-11-24)
- Added rolling event store for PAST events.
- Unified `eventsData` and `newsConfig.events` bindings.
- Added active profile label to Scan Controls.

## v0.14.0 (2026-11-23)
- Multi-profile support (ND100, XAUUSD) with independent schedules.
- Profile-specific busy/quiet hours and intervals.
- Telegram messages tagged with profile name.
- Stale scan detection and alerts.

## v0.13.0 (2026-11-22)
- Account number display on Dashboard.
- Economic Events card on Dashboard.
- EA v0.11.4: Fixed `AccountInfoInteger` compilation error.
