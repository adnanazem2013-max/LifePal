# LifePal — Local Edition V2

Open **index.html** in Chrome or Edge. No installation, login, npm, Supabase, API keys, internet connection, or build step is required to use the supplied app.

This version follows the supplied dark business-dashboard reference. The interface is English only. All icons are inline SVG drawings; no emoji, external fonts, CDNs, or image downloads are used.

## Included

- Immediate access to separate Personal and Business workspaces.
- Projects and tasks with creation, editing, completion, priorities, dates, and filtering.
- CRM opportunities and a calculated sales pipeline chart.
- A local team contact directory (no invitations or access permissions).
- Goals, monthly calendar with previous/next navigation, events, and notes.
- Manual transaction records and clearly labeled demo card designs.
- Reusable manual workflow checklists.
- Calculated summaries and reports; no simulated AI response.
- Search within the active workspace, recent activity, and in-app reminders.
- Five themes, accent colors, compact layout, dashboard sections and pinned shortcuts.
- Browser persistence, JSON export/import, and clearing the current workspace after confirmation.

## Saving your data

The app uses browser localStorage when available. Records remain on this browser/device, and anyone using the same browser profile can access them. The two workspaces are logically separate, not protected accounts. This is intentionally a local app without authentication or a backend.

Browser behavior for file:// storage varies. Keep index.html in the same location, use the same browser, and export backups from Settings. If storage is blocked or full, the app clearly reports a temporary session. It does not overwrite unreadable saved data. Changes from another tab are detected before saving, to avoid overwriting them.

For more consistent storage, serve the folder with a local static server, for example `python -m http.server 8080`, and always use the same localhost URL. Clearing browser data removes local records. JSON backups include both workspaces and settings.

## Editing the code

- `index.html`: complete self-contained runnable application.
- `app.js`: readable application source.
- `style.css`: readable design source.
- `build.py`: rebuilds index.html after changes (`python build.py`).
- `test.cjs`: automated checks (`node --test test.cjs`); Node is required only to run these checks.

Do not edit app.js or style.css and expect the existing index.html to update automatically; rebuild it or edit its embedded code directly.

To upload manually to an existing GitHub project, place index.html in the desired static-site root. No repository was changed and no hosted site was published by this delivery. Keep the previous Supabase version separately if you want to reintroduce accounts later; this local edition does not access its tables or weaken its RLS.

## Financial and collaboration boundaries

All starting records are illustrative samples. Amounts are manually entered USD values. Card colors, limits and freeze controls affect only previews; there are no real financial products, payments, bank feeds or Visa/Mastercard cards. Team entries are contacts, not accounts. Workflows are manual checklists, not scheduled automations. Notifications run only while the app is open. Export before storing anything you cannot replace.

## Verification performed

- JavaScript syntax checked successfully.
- Seven automated checks: all 15 pages render; data survives app initialization; workspace separation; corrupted storage preservation; cross-tab overwrite prevention; HTML escaping and backup validation; dashboard calculations.
- Desktop browser: direct dashboard entry without login; task creation; task persistence after reload; switching to Personal and back; selecting Royal Purple and restoring Midnight Blue; desktop visual review.
- Responsive CSS is included. A phone/tablet browser viewport test was not performed.
- File-double-click behavior and browser download/import dialogs were not manually tested here. The app is self-contained with no module imports or network requests, but persistence depends on browser policy as noted above.
