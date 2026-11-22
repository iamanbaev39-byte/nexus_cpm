document.addEventListener("DOMContentLoaded", () => {
  const currentPath = window.location.pathname;

  document.querySelectorAll(".nav-links a").forEach((link) => {
    const href = link.getAttribute("href");
    if (href && href !== "/" && currentPath.startsWith(href)) {
      link.classList.add("active");
    } else if (href === "/" && currentPath === "/") {
      link.classList.add("active");
    }
  });

  document.querySelectorAll(".alert").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 4500);
  });

  document.querySelectorAll(".btn, .nav-links a").forEach((element) => {
    element.addEventListener("click", (event) => {
      const rect = element.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const ripple = document.createElement("span");
      ripple.className = "ripple";
      ripple.style.width = `${size}px`;
      ripple.style.height = `${size}px`;
      ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
      ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
      element.appendChild(ripple);
      setTimeout(() => ripple.remove(), 550);
    });
  });
});