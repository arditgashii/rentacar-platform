# Intentional bugs

DriveNow exists to be tested, so it ships with four realistic bugs. They are switched on by
`DRIVENOW_BUGS=on` (the default) and disappear with `DRIVENOW_BUGS=off`. Each one sits inside the
normal code path, guarded by the flag, and is marked with a `BUG-00x` comment.

The test suite in [rentacar-qa-automation](https://github.com/arditgashii/rentacar-qa-automation)
catches every one of them; with the flag off the whole suite passes.

| ID | Where | What happens | What should happen | Caught by |
|---|---|---|---|---|
| BUG-001 | `app/services/cars.py`, `update_car` (API `PUT`/`PATCH /api/v1/cars/{id}` and the edit page) | When a car is updated, `daily_price` is cut to a whole number: 89.99 is saved as 89.00. Creating a car stores the right price, so the bug only shows up on edit. | The price is saved exactly as entered. | TC-005 |
| BUG-002 | `app/services/bookings.py`, `_overlap_condition` | The overlap check only asks whether the new pickup date falls inside an existing booking. A new booking that starts before an existing one and ends after it is accepted, so the car is double booked. | Two pending or confirmed bookings of the same car never share a day (`start < other_end and other_start < end`). The API answers 409 `DATES_TAKEN`. | TC-008 |
| BUG-003 | `app/services/cars.py`, `delete_car` (API `DELETE /api/v1/cars/{id}`) | The API only checks that someone is logged in, not that they own the car. The web UI hides the delete button from other users, so the hole is only visible through the API. | Only the owner or an admin can delete a car; anyone else gets 403 `FORBIDDEN` and the car stays. | TC-009 |
| BUG-004 | `app/services/cars.py`, `list_cars` (API `GET /api/v1/cars?max_price=` and the price filter on `/cars`) | `max_price` is applied as "less than" instead of "less than or equal", so a car priced exactly at the limit is missing from the results. | `max_price` is inclusive, like `min_price`. | TC-006 |

## Reproduce by hand

With the stack running (`docker compose up -d`) and a client token in `$TOKEN`:

```bash
# BUG-004: the Tesla costs 89.99 but is not found with max_price=89.99
curl "http://localhost:8000/api/v1/cars?min_price=89.99&max_price=89.99"

# BUG-001: update any of your cars with "daily_price": 89.99, the response says 89.0
curl -X PATCH http://localhost:8000/api/v1/cars/<id> -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"daily_price": 89.99}'
```

Restart with `DRIVENOW_BUGS=off docker compose up -d` and the same calls behave correctly.
