(() => {
  let currentPage = 1;
  const totalPages = 5;

  const showPage = (pageNum) => {
    document.querySelectorAll(".form-page").forEach((page) => page.classList.remove("active"));
    const target = document.getElementById(`page${pageNum}`);
    if (target) target.classList.add("active");
    document.querySelectorAll(".step-pill").forEach((pill) => {
      pill.classList.toggle("active", Number(pill.dataset.step) === pageNum);
    });
    currentPage = pageNum;
  };

  window.nextPage = () => {
    if (currentPage < totalPages) showPage(currentPage + 1);
  };

  window.prevPage = () => {
    if (currentPage > 1) showPage(currentPage - 1);
  };

  window.updateTimeFields = () => {
    const datetime = document.getElementById("datetime")?.value;
    if (!datetime) return;
    const date = new Date(datetime);
    document.getElementById("hour").value = date.getHours();
    document.getElementById("day").value = date.getDate();
    document.getElementById("month").value = date.getMonth() + 1;
    document.getElementById("day_of_week").value = date.getDay();
    document.getElementById("is_weekend").value =
      date.getDay() === 0 || date.getDay() === 6 ? 1 : 0;
  };

  window.addEventListener("DOMContentLoaded", () => {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    const localTime = new Date(now.getTime() - offset);
    const datetime = document.getElementById("datetime");
    if (datetime) {
      datetime.value = localTime.toISOString().slice(0, 16);
      window.updateTimeFields();
    }
    showPage(1);
  });
})();
