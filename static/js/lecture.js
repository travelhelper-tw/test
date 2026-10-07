const toggle = document.getElementById("sidebar-toggle");
const sidebar = document.getElementById("course-sidebar");

if (toggle && sidebar) {
  const mobile = window.matchMedia("(max-width: 760px)");
  const setExpanded = (expanded) => {
    toggle.setAttribute("aria-expanded", String(expanded));
    sidebar.hidden = !expanded;
  };
  const updateLayout = () => {
    toggle.hidden = !mobile.matches;
    setExpanded(!mobile.matches);
  };
  toggle.addEventListener("click", () => {
    setExpanded(toggle.getAttribute("aria-expanded") !== "true");
  });
  mobile.addEventListener("change", updateLayout);
  updateLayout();
}
