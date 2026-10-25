# Decisions

Choices made while building DriveNow, with the reason for each.

- **Service Bus topic instead of a queue.** Booking events go to the topic `booking-events` with two
  subscriptions: `notifications`, consumed by the worker, and `audit`, consumed by nobody. Tests peek
  `audit` to prove an event was published without racing the worker for the message.
- **The API and the web UI share the service layer.** Routes only translate HTTP to service calls, so
  a business rule (and an intentional bug) behaves the same in the UI and in the API.
- **Separate authentication for API and UI.** The API reads only `Authorization: Bearer`; the UI
  reads only an HttpOnly cookie and checks a CSRF token on every form. A cookie can never be used to
  call the API from another site.
- **Async everywhere.** FastAPI endpoints, SQLAlchemy (`aioodbc` for SQL Server, `aiosqlite` for
  local runs), the Blob Storage client and the Service Bus client are all async, so no request blocks
  the event loop.
- **SQLite and memory backends for local runs.** `STORAGE_BACKEND=local` and
  `MESSAGING_BACKEND=memory` make the unit tests and a quick local start possible without Docker. The
  Docker stack and CI use the real emulators.
- **Photos are served through `/media/{blob}`.** Browsers and tests never talk to Azurite directly,
  and only names that match `cars/<id>/<32 hex>.(jpg|png|webp)` are served (no path traversal).
- **Photos are checked by content.** Pillow opens and verifies every upload; the file name and the
  declared content type are ignored.
- **The LLM output is never trusted.** A generated description that is too long, mentions money or
  misses the make, model or year is replaced by the deterministic mock text.
- **Confirmation dialogs are in-page `<dialog>` elements**, not `window.confirm`, so automated tests
  can click them.
- **Seed photos are drawn with Pillow**, so the repository has no downloaded images and no
  licensing questions.
- **Bookings are half-open ranges** `[start_date, end_date)`: a car returned on a day can be picked
  up by the next client the same day.
