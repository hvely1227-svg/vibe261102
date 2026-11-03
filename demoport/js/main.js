(function () {
  // ----- 프로젝트 카드 렌더링 -----
  function renderProjects() {
    const list = document.getElementById("project-list");
    if (!list || typeof PROJECTS === "undefined") return;

    PROJECTS.forEach((p) => {
      const card = document.createElement("article");
      card.className = "project-card";

      const title = document.createElement("h3");
      title.textContent = p.title;

      const desc = document.createElement("p");
      desc.textContent = p.description;

      const tags = document.createElement("ul");
      tags.className = "tags";
      tags.setAttribute("aria-label", "사용 기술");
      p.tags.forEach((t) => {
        const li = document.createElement("li");
        li.textContent = t;
        tags.appendChild(li);
      });

      const links = document.createElement("div");
      links.className = "project-links";
      if (p.github) links.appendChild(makeLink(p.github, "GitHub"));
      if (p.demo) links.appendChild(makeLink(p.demo, "Demo"));

      card.append(title, desc, tags, links);
      list.appendChild(card);
    });
  }

  function makeLink(href, label) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = label;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }

  // ----- 모바일 메뉴 -----
  function setupNav() {
    const toggle = document.querySelector(".nav-toggle");
    const menu = document.getElementById("nav-menu");
    if (!toggle || !menu) return;

    function setOpen(open) {
      menu.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    }

    toggle.addEventListener("click", () => setOpen(!menu.classList.contains("open")));
    menu.addEventListener("click", (e) => {
      if (e.target.tagName === "A") setOpen(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") setOpen(false);
    });
  }

  // ----- 현재 섹션 메뉴 강조 -----
  function setupActiveLink() {
    const links = document.querySelectorAll(".nav-menu a");
    const sections = [...links].map((a) => document.querySelector(a.getAttribute("href")));
    if (!("IntersectionObserver" in window)) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          links.forEach((a) =>
            a.classList.toggle("active", a.getAttribute("href") === "#" + entry.target.id)
          );
        });
      },
      { rootMargin: "-40% 0px -55% 0px" }
    );
    sections.forEach((s) => s && observer.observe(s));
  }

  // ----- 이메일 복사 -----
  function setupCopyEmail() {
    const btn = document.getElementById("copy-email");
    const status = document.getElementById("copy-status");
    if (!btn) return;

    btn.addEventListener("click", async () => {
      const email = btn.dataset.email;
      try {
        await navigator.clipboard.writeText(email);
        status.textContent = "이메일 주소가 복사되었습니다.";
      } catch (e) {
        status.textContent = "복사에 실패했습니다. 직접 선택해 복사해 주세요: " + email;
      }
      setTimeout(() => (status.textContent = ""), 3000);
    });
  }

  // ----- 다크 모드 -----
  function setupTheme() {
    const btn = document.querySelector(".theme-toggle");
    if (!btn) return;

    btn.addEventListener("click", () => {
      const root = document.documentElement;
      const current =
        root.getAttribute("data-theme") ||
        (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem("theme", next);
      } catch (e) {}
    });
  }

  document.getElementById("year").textContent = new Date().getFullYear();
  renderProjects();
  setupNav();
  setupActiveLink();
  setupCopyEmail();
  setupTheme();
})();
