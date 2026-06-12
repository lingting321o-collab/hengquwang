const state = { user: null, products: [] };

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}

const toast = document.querySelector(".toast");
let toastTimer;
function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2400);
}

const slides = [...document.querySelectorAll(".slide")];
const dots = [...document.querySelectorAll(".slider-dots button")];
let currentSlide = 0;
let sliderTimer;
function showSlide(index) {
  currentSlide = (index + slides.length) % slides.length;
  slides.forEach((slide, i) => slide.classList.toggle("active", i === currentSlide));
  dots.forEach((dot, i) => dot.classList.toggle("active", i === currentSlide));
}
function startSlider() {
  clearInterval(sliderTimer);
  sliderTimer = setInterval(() => showSlide(currentSlide + 1), 4500);
}
dots.forEach((dot, index) => dot.addEventListener("click", () => {
  showSlide(index);
  startSlider();
}));
startSlider();

const processData = {
  test: [["提交需求","在线选择测试项目，填写样品信息与测试要求"],["确认方案","技术顾问沟通细节，确认测试方法与报价"],["寄送样品","按规范完成样品制备并寄送至实验室"],["实验测试","专业工程师操作设备，全程跟踪测试进度"],["数据审核","测试数据经过质量审核后生成规范报告"],["交付结果","线上交付数据与报告，支持售后技术答疑"]],
  draw: [["提交资料","上传论文内容、参考图与目标期刊风格"],["需求沟通","科研绘图顾问确认构图、尺寸与交付周期"],["草图设计","设计师输出结构草图并进行首轮确认"],["精细制作","完成专业配色、模型细化与视觉表达"],["修改确认","根据反馈进行细节调整与最终校对"],["文件交付","交付高清图片与可编辑源文件"]],
  analysis: [["问题评估","描述研究问题并提交原始数据与分析目标"],["方案设计","分析师确定模型、算法和统计分析路径"],["数据处理","完成数据清洗、标准化与质量检查"],["计算分析","执行模拟计算、统计检验或机器学习任务"],["结果复核","由项目负责人复核数据与结论可靠性"],["报告交付","交付图表、分析报告与必要的方法说明"]]
};
const processGrid = document.querySelector("#processGrid");
const processButtons = [...document.querySelectorAll(".process-tabs button")];
function renderProcess(type) {
  processGrid.innerHTML = processData[type].map((item, index) => `
    <article class="process-card"><b>0${index + 1}</b><h3>${item[0]}</h3><p>${item[1]}</p></article>
  `).join("");
}
processButtons.forEach((button) => button.addEventListener("click", () => {
  processButtons.forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  renderProcess(button.dataset.tab);
}));
renderProcess("test");

document.querySelectorAll(".result-tabs button").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".result-tabs button").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  showToast(`已切换至“${button.textContent}”`);
}));

const productGrid = document.querySelector("#productGrid");
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}
function renderProducts(items) {
  productGrid.innerHTML = items.length ? items.map((item) => `
    <article class="product-card">
      <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}">
      <div>
        <h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.instrument)}</p>
        <button class="reserve-trigger" data-product="${item.id}" type="button">立即预约</button>
        <small>已测试 <em>${item.tested_count}</em> 次</small>
        <small>平均 <em>${escapeHtml(item.turnaround)}</em> 工作日完成</small>
        <small><em>${escapeHtml(item.satisfaction)}</em> 对结果满意</small>
      </div>
    </article>`).join("") : '<p class="empty-state">没有找到匹配的科研项目</p>';
}
async function loadProducts(keyword = "") {
  productGrid.innerHTML = '<p class="loading-state">正在加载科研项目...</p>';
  try {
    const data = await api(`/api/products?q=${encodeURIComponent(keyword)}`);
    state.products = data.items;
    renderProducts(data.items);
  } catch (error) {
    productGrid.innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  }
}

const modalBackdrop = document.querySelector("#modalBackdrop");
const modalTitle = document.querySelector("#modalTitle");
const modalIntro = document.querySelector("#modalIntro");
const modalForm = document.querySelector("#modalForm");
function field(name, label, type = "text", options = {}) {
  const full = options.full ? " full" : "";
  const required = options.required === false ? "" : " required";
  const value = escapeHtml(options.value || "");
  if (type === "textarea") return `<div class="form-field${full}"><label>${label}</label><textarea name="${name}"${required}>${value}</textarea></div>`;
  if (type === "select") return `<div class="form-field${full}"><label>${label}</label><select name="${name}"${required}>${options.items.map((item) => `<option>${escapeHtml(item)}</option>`).join("")}</select></div>`;
  return `<div class="form-field${full}"><label>${label}</label><input name="${name}" type="${type}" value="${value}"${required}></div>`;
}
function openModal(title, intro, body, submitLabel, onSubmit) {
  modalTitle.textContent = title;
  modalIntro.textContent = intro;
  modalForm.innerHTML = `<div class="form-grid">${body}</div><button class="modal-submit" type="submit">${submitLabel}</button>`;
  modalForm.onsubmit = async (event) => {
    event.preventDefault();
    const button = modalForm.querySelector(".modal-submit");
    button.disabled = true;
    button.textContent = "提交中...";
    try {
      await onSubmit(Object.fromEntries(new FormData(modalForm)));
    } catch (error) {
      showToast(error.message);
      button.disabled = false;
      button.textContent = submitLabel;
    }
  };
  modalBackdrop.hidden = false;
  document.body.style.overflow = "hidden";
  setTimeout(() => modalForm.querySelector("input,select,textarea")?.focus(), 0);
}
function closeModal() {
  modalBackdrop.hidden = true;
  document.body.style.overflow = "";
}
document.querySelector(".modal-close").addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", (event) => {
  if (event.target === modalBackdrop) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !modalBackdrop.hidden) closeModal();
});

function openLogin() {
  openModal("登录", "登录后可以预约测试并查看订单进度。",
    field("email", "邮箱", "email", { full: true }) + field("password", "密码", "password", { full: true }),
    "登录", async (data) => {
      const result = await api("/api/login", { method: "POST", body: JSON.stringify(data) });
      state.user = result.user;
      updateAuth();
      closeModal();
      showToast("登录成功");
    });
}
function openRegister() {
  openModal("注册账号", "创建账号后即可使用预约、需求和订单管理功能。",
    field("name", "姓名") + field("phone", "手机号") + field("email", "邮箱", "email", { full: true }) + field("password", "密码（至少8位）", "password", { full: true }),
    "注册并登录", async (data) => {
      const result = await api("/api/register", { method: "POST", body: JSON.stringify(data) });
      state.user = result.user;
      updateAuth();
      closeModal();
      showToast("注册成功");
    });
}
function ensureLogin(action) {
  if (state.user) return true;
  showToast(`请先登录后${action}`);
  openLogin();
  return false;
}
function openReservation(productId) {
  if (!ensureLogin("预约")) return;
  const product = state.products.find((item) => item.id === Number(productId));
  openModal("预约科研服务", product?.title || "科研测试项目",
    field("product_id", "项目编号", "hidden", { value: productId }) +
    field("contact_name", "联系人", "text", { value: state.user.name }) +
    field("phone", "手机号", "tel", { value: state.user.phone }) +
    field("organization", "学校 / 单位", "text", { full: true, required: false }) +
    field("sample_info", "样品信息", "textarea", { full: true }) +
    field("requirements", "测试要求", "textarea", { full: true, required: false }),
    "提交预约", async (data) => {
      const result = await api("/api/reservations", { method: "POST", body: JSON.stringify(data) });
      closeModal();
      showToast(`预约成功，订单号：${result.order_no}`);
    });
}
function openDemand() {
  if (!ensureLogin("发布需求")) return;
  openModal("发布科研需求", "提交后服务顾问会尽快联系您确认方案。",
    field("title", "需求标题", "text", { full: true }) +
    field("category", "服务类型", "select", { items: ["材料测试","生物服务","环境检测","模拟计算","科研绘图","数据分析","论文服务"] }) +
    field("budget", "预算", "text", { required: false }) +
    field("contact_name", "联系人", "text", { value: state.user.name }) +
    field("phone", "手机号", "tel", { value: state.user.phone }) +
    field("details", "需求详情", "textarea", { full: true }),
    "提交需求", async (data) => {
      const result = await api("/api/demands", { method: "POST", body: JSON.stringify(data) });
      closeModal();
      showToast(`需求已提交，编号：${result.demand_no}`);
    });
}
function openInquiry() {
  openModal("在线咨询", "请留下联系方式和问题，我们会尽快回复。",
    field("name", "姓名", "text", { value: state.user?.name || "" }) +
    field("phone", "手机号", "tel", { value: state.user?.phone || "" }) +
    field("message", "咨询内容", "textarea", { full: true }),
    "提交咨询", async (data) => {
      await api("/api/inquiries", { method: "POST", body: JSON.stringify(data) });
      closeModal();
      showToast("咨询已提交");
    });
}

const authArea = document.querySelector("#authArea");
function updateAuth() {
  if (!state.user) {
    authArea.innerHTML = '<button type="button" data-auth="login">登录</button><i></i><button type="button" data-auth="register">注册</button>';
    return;
  }
  authArea.innerHTML = `<a href="/account">${escapeHtml(state.user.name)}</a><i></i>${state.user.role === "admin" ? '<a href="/admin">后台</a><i></i>' : ""}<button type="button" data-auth="logout">退出</button>`;
}
authArea.addEventListener("click", async (event) => {
  const action = event.target.dataset.auth;
  if (action === "login") openLogin();
  if (action === "register") openRegister();
  if (action === "logout") {
    await api("/api/logout", { method: "POST", body: "{}" });
    state.user = null;
    updateAuth();
    showToast("已退出登录");
  }
});
productGrid.addEventListener("click", (event) => {
  const button = event.target.closest(".reserve-trigger");
  if (button) openReservation(button.dataset.product);
});
document.querySelectorAll(".demand-trigger").forEach((button) => button.addEventListener("click", openDemand));
document.querySelector("#inquiryTrigger").addEventListener("click", openInquiry);
document.querySelectorAll(".inquiry-trigger").forEach((button) => button.addEventListener("click", openInquiry));

const searchForm = document.querySelector("#searchForm");
const searchInput = document.querySelector("#searchInput");
searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadProducts(searchInput.value.trim());
  document.querySelector("#hot").scrollIntoView({ behavior: "smooth" });
});
document.querySelectorAll("[data-search]").forEach((button) => button.addEventListener("click", () => {
  searchInput.value = button.dataset.search;
  searchForm.requestSubmit();
}));
document.querySelector(".footer-search").addEventListener("submit", (event) => {
  event.preventDefault();
  searchInput.value = event.currentTarget.querySelector("input").value.trim();
  searchForm.requestSubmit();
});

const menuToggle = document.querySelector(".menu-toggle");
const mainNav = document.querySelector(".main-nav");
menuToggle.addEventListener("click", () => {
  const isOpen = mainNav.classList.toggle("open");
  menuToggle.setAttribute("aria-expanded", String(isOpen));
});
mainNav.addEventListener("click", () => {
  mainNav.classList.remove("open");
  menuToggle.setAttribute("aria-expanded", "false");
});

async function initialize() {
  try {
    const [{ user }] = await Promise.all([api("/api/me"), loadProducts()]);
    state.user = user;
    updateAuth();
  } catch (error) {
    showToast(error.message);
  }
}
initialize();
