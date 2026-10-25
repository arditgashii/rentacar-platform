# data-testid reference

Every interactive element and every value a test reads has a stable `data-testid` in kebab-case. `{id}` is the database id of the car, photo, booking or user. This list is generated from the templates; keep it in sync when a template changes.

Patterns:

- `{field}` is the form field name with `_` replaced by `-`: `filter-city`, `filter-category`,
  `filter-transmission`, `filter-fuel-type`; `car-form-make`, `car-form-daily-price`,
  `car-form-license-plate`, `car-form-error-daily-price`, `register-error-email`.
- `{feature}` is a feature value: `car-feature-gps`, `car-form-feature-air_conditioning`.
- `{change}` is `activate`, `deactivate`, `make-admin` or `make-client`.

## `base.html`

- `confirm-dialog`
- `confirm-message`
- `confirm-no`
- `confirm-yes`
- `flash-{success|error}`
- `nav-admin`
- `nav-admin-bookings`
- `nav-admin-cars`
- `nav-admin-users`
- `nav-cars`
- `nav-login`
- `nav-logo`
- `nav-logout`
- `nav-my-bookings`
- `nav-my-listings`
- `nav-new-car`
- `nav-register`
- `nav-toggle`
- `nav-user-name`
- `navbar`

## `home.html`

- `home-featured`
- `home-search`
- `home-search-category`
- `home-search-city`
- `home-search-submit`
- `home-see-all`

## `_car_card.html`

- `car-card-price`
- `car-card-title`
- `car-card-{id}`

## `login.html`

- `login-email`
- `login-error`
- `login-form`
- `login-password`
- `login-register-link`
- `login-submit`

## `register.html`

- `register-city`
- `register-email`
- `register-error-{field}`
- `register-form`
- `register-full-name`
- `register-password`
- `register-phone`
- `register-submit`

## `error.html`

- `error-message`
- `error-page`

## `cars/list.html`

- `cars-empty`
- `cars-grid`
- `cars-total`
- `filter-apply`
- `filter-clear`
- `filter-max-price`
- `filter-min-price`
- `filter-q`
- `filter-seats`
- `filter-sort`
- `filter-{field}`
- `filters`
- `filters-box`
- `filters-toggle`
- `pagination`
- `pagination-current`
- `pagination-next`
- `pagination-prev`

## `cars/detail.html`

- `booking-box`
- `booking-end`
- `booking-form`
- `booking-login`
- `booking-start`
- `booking-submit`
- `booking-total`
- `car-category`
- `car-city`
- `car-color`
- `car-daily-price`
- `car-deposit`
- `car-description`
- `car-doors`
- `car-edit-link`
- `car-feature-{feature}`
- `car-features`
- `car-fuel-type`
- `car-gallery`
- `car-main-photo`
- `car-mileage`
- `car-owner`
- `car-pickup`
- `car-plate`
- `car-seats`
- `car-specs`
- `car-status`
- `car-thumb-{id}`
- `car-title`
- `car-transmission`

## `cars/form.html`

- `car-delete`
- `car-delete-form`
- `car-form`
- `car-form-cancel`
- `car-form-description`
- `car-form-error-{field}`
- `car-form-feature-{feature}`
- `car-form-features`
- `car-form-generate-description`
- `car-form-photos`
- `car-form-submit`
- `car-form-view`
- `car-form-{field}`
- `photo-delete-{id}`
- `photo-down-{id}`
- `photo-item-{id}`
- `photo-make-primary-{id}`
- `photo-manager`
- `photo-primary-badge`
- `photo-up-{id}`
- `photo-upload-form`
- `photo-upload-input`
- `photo-upload-submit`
- `photos-empty`

## `_bookings_table.html`

- `booking-cancel-{id}`
- `booking-confirm-{id}`
- `booking-row-{id}`
- `booking-status-{id}`
- `booking-total-{id}`
- `bookings-table`

## `my/listings.html`

- `my-listing-edit-{id}`
- `my-listing-row-{id}`
- `my-listings-empty`
- `my-listings-new`
- `my-listings-table`

## `my/bookings.html`

- `my-bookings-empty`

## `admin/dashboard.html`

- `admin-all-bookings`
- `admin-no-bookings`
- `admin-stats`
- `stat-active-bookings`
- `stat-cars`
- `stat-revenue`
- `stat-users`

## `admin/cars.html`

- `admin-cars-apply`
- `admin-cars-delete-{id}`
- `admin-cars-edit-{id}`
- `admin-cars-empty`
- `admin-cars-filters`
- `admin-cars-new`
- `admin-cars-price-{id}`
- `admin-cars-row-{id}`
- `admin-cars-search`
- `admin-cars-status`
- `admin-cars-table`
- `admin-cars-title-{id}`
- `admin-cars-total`

## `admin/users.html`

- `admin-users-role-{id}`
- `admin-users-row-{id}`
- `admin-users-status-{id}`
- `admin-users-table`
- `admin-users-{change}-{id}`

## `admin/bookings.html`

- `admin-bookings-empty`
