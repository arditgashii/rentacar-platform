// Small progressive enhancements. Every page works without this file.

// Mobile menu
document.querySelector(".nav-toggle")?.addEventListener("click", (event) => {
  const open = document.body.classList.toggle("nav-open");
  event.currentTarget.setAttribute("aria-expanded", String(open));
});

// Filters start folded on small screens, so the results come first
const filtersBox = document.querySelector(".filters-box");
if (filtersBox && window.matchMedia("(max-width: 900px)").matches) filtersBox.open = false;

// Confirmation dialog for forms with data-confirm (an in-page dialog, so automated tests can click it)
const dialog = document.querySelector(".confirm-dialog");
let pendingForm = null;
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (form.dataset.confirmed === "yes") return;
    event.preventDefault();
    pendingForm = form;
    dialog.querySelector("p").textContent = form.dataset.confirm;
    dialog.showModal();
  });
});
dialog?.querySelector("[data-confirm-yes]").addEventListener("click", () => {
  dialog.close();
  if (pendingForm) {
    pendingForm.dataset.confirmed = "yes";
    pendingForm.requestSubmit();
  }
});
dialog?.querySelector("[data-confirm-no]").addEventListener("click", () => {
  pendingForm = null;
  dialog.close();
});

// Photo gallery on the car page
document.querySelectorAll(".gallery .thumb").forEach((thumb) => {
  thumb.addEventListener("click", () => {
    document.querySelector(".gallery-main").src = thumb.dataset.src;
    document.querySelectorAll(".gallery .thumb").forEach((t) => t.classList.toggle("active", t === thumb));
  });
});

// Live booking total
const bookingForm = document.querySelector(".booking-form");
if (bookingForm) {
  const price = Number(bookingForm.dataset.price);
  const start = bookingForm.querySelector("[name=start_date]");
  const end = bookingForm.querySelector("[name=end_date]");
  const total = bookingForm.querySelector("[data-testid=booking-total]");
  const update = () => {
    const days = Math.round((new Date(end.value) - new Date(start.value)) / 86400000);
    total.textContent = days > 0
      ? `€${(price * days).toLocaleString("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} for ${days} ${days === 1 ? "day" : "days"}`
      : "Choose a return date after the pickup date";
  };
  start.addEventListener("change", update);
  end.addEventListener("change", update);
  update();
}

// Generate description
document.querySelectorAll("[data-describe]").forEach((button) => {
  button.addEventListener("click", async () => {
    const textarea = document.querySelector("textarea[name=description]");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Writing...";
    try {
      const response = await fetch(button.dataset.describe, {
        method: "POST",
        headers: { "X-CSRF-Token": document.getElementById("csrf").value },
      });
      if (!response.ok) throw new Error(String(response.status));
      textarea.value = (await response.json()).description;
    } catch {
      button.textContent = "Could not generate, try again";
      button.disabled = false;
      return;
    }
    button.textContent = original;
    button.disabled = false;
  });
});
